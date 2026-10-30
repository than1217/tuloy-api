import argparse
import csv
import json
import os
import sys
import tempfile
import time
import threading
import concurrent.futures
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from tqdm import tqdm

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
load_dotenv(dotenv_path=os.path.join(PROJECT_DIR, ".env"), override=True)

CHECKPOINT_COLUMNS = (
    "TULOY ID",
    "MEMBER ID",
    "VERIFY STATUS",
    "TESDA POST STATUS",
    "IMPORT ERROR",
)

class RequestTimeout(RuntimeError):
    pass

class ApiRequestError(RuntimeError):
    pass

def parse_date(value, field_name):
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field_name} is required")
    for date_format in ("%Y-%b-%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"Invalid {field_name} date: {value!r}")

def parse_optional_date(value, field_name):
    value = (value or "").strip()
    return parse_date(value, field_name) if value else None

def read_json_response(response):
    return json.loads(response.read().decode("utf-8"))

class ApiClient:
    def __init__(self, base_url, username, password, timeout):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.access_token = None
        self.refresh_token = None
        self.auth_lock = threading.Lock()

    def _request(self, path, body, content_type, authenticated=True, retry_auth=True):
        headers = {"Content-Type": content_type}
        request_token = None
        if authenticated:
            with self.auth_lock:
                if not self.access_token:
                    self.login()
                request_token = self.access_token
            # Note: Changed to standard Bearer token scheme
            headers["Authorization"] = "Bearer " + str(request_token)

        request = Request(
            f"{self.base_url}/{path.lstrip('/')}",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return read_json_response(response)
        except HTTPError as error:
            response_body = error.read().decode("utf-8", errors="replace")
            if authenticated and error.code == 401 and retry_auth:
                with self.auth_lock:
                    if self.access_token == request_token:
                        self.refresh()
                return self._request(path, body, content_type, retry_auth=False)
            raise ApiRequestError(
                f"POST {path} failed with HTTP {error.code}: {response_body}"
            ) from error
        except TimeoutError as error:
            raise RequestTimeout(
                f"POST {path} timed out after {self.timeout:g} seconds"
            ) from error
        except URLError as error:
            raise RuntimeError(
                f"Could not reach {self.base_url}: {error.reason}"
            ) from error

    def login(self):
        if not self.username or not self.password:
            raise RuntimeError(
                "Set TULOY_API_USERNAME and TULOY_API_PASSWORD, "
                "or pass --username and --password."
            )
        response = self._request(
            "/token",
            urlencode(
                {"username": self.username, "password": self.password}
            ).encode("utf-8"),
            "application/x-www-form-urlencoded",
            authenticated=False,
        )
        self.access_token = response["access_token"]
        self.refresh_token = response.get("refresh_token")

    def refresh(self):
        if not self.refresh_token:
            self.login()
            return

        request = Request(
            f"{self.base_url}/refresh",
            data=json.dumps({"refresh_token": self.refresh_token}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                token_data = read_json_response(response)
                self.access_token = token_data["access_token"]
                self.refresh_token = token_data.get("refresh_token", self.refresh_token)
        except TimeoutError as error:
            raise RequestTimeout(
                f"POST /refresh timed out after {self.timeout:g} seconds"
            ) from error
        except (HTTPError, URLError):
            self.login()

    def post_json(self, path, payload):
        return self._request(
            path,
            json.dumps(payload).encode("utf-8"),
            "application/json",
        )

def verify_payload(row):
    payload = {
        "first_name": (row.get("FIRST NAME") or "").strip(),
        "last_name": (row.get("LAST NAME") or "").strip(),
        "date_of_birth": parse_date(row.get("BIRTHDATE"), "BIRTHDATE"),
    }
    if not payload["first_name"] or not payload["last_name"]:
        raise ValueError("FIRST NAME and LAST NAME are required")
    return payload

def tesda_payload(row):
    verified = (row.get("VERIFY STATUS") or "").strip()
    if verified not in ("Matched", "Not Found", "Multiple Match Found"):
        raise ValueError(f"Unexpected verification status: {verified!r}")
    matched = verified == "Matched"

    data = None
    if matched:
        tuloy_id = (row.get("TULOY ID") or "").strip()
        if not tuloy_id:
            raise ValueError("Verification says Matched but TULOY ID is empty")
        if len(tuloy_id) > 50:
            raise ValueError("TULOY ID exceeds the database limit of 50 characters")

        member_id_value = (row.get("MEMBER ID") or "").strip()
        if not member_id_value:
            raise ValueError("Verification says Matched but MEMBER ID is empty")
        try:
            member_id = int(member_id_value)
        except ValueError as error:
            raise ValueError("MEMBER ID must be an unsigned integer") from error
        if not 1 <= member_id <= 4294967295:
            raise ValueError("MEMBER ID must be between 1 and 4294967295")
        uli = (row.get("ULI") or "").strip() or None
        if uli and len(uli) > 50:
            raise ValueError("ULI exceeds the database limit of 50 characters")
        
        qualification = (row.get("QUALIFICATION") or "").strip()
        start_date = (row.get("START DATE") or "").strip()
        end_date = (row.get("END DATE") or "").strip()
        training_status = (row.get("TRAINING STATUS") or "").strip()
        
        has_short_course = bool(qualification or start_date or end_date or training_status)
        short_course_data = None
        
        if has_short_course:
            short_course_data = {
                "program_name": qualification or None,
                "start_date": parse_optional_date(start_date, "START DATE"),
                "end_date": parse_optional_date(end_date, "END DATE"),
                "training_status": training_status or None,
            }
        
        data = {
            "id": tuloy_id,
            "member_id": member_id,
            "uli": uli,
            "mothers_maiden": None,
            "diploma": None,
            "short_course": short_course_data,
            "enrollment_status": None,
            "date_encoded": None,
            "date_updated": None,
        }

    message = "FOUND" if matched else verified.upper()
    return {
        "status": matched,
        "message": message,
        "data": data,
        "error_code": None,
        "enrollment_id": 0,
    }

def process_row_task(row, client, args):
    v_succ, p_succ, fail = 0, 0, 0
    try:
        # Verification Step
        if args.reverify or not (row.get("VERIFY STATUS") or "").strip():
            if args.reverify:
                row["VERIFY STATUS"] = ""
                row["TULOY ID"] = ""
                row["MEMBER ID"] = ""
                row["TESDA POST STATUS"] = ""
            try:
                result = client.post_json("/VerifyMemberBene", verify_payload(row))
                status = result.get("status")
                if status not in ("Matched", "Not Found", "Multiple Match Found"):
                    raise RuntimeError(f"Unexpected verification response: {result!r}")
                if status == "Matched" and (
                    result.get("tuloy_id") is None or result.get("member_id") is None
                ):
                    raise RuntimeError("Verification returned Matched without both IDs")
                row["VERIFY STATUS"] = status
                tuloy_id = result.get("tuloy_id")
                member_id = result.get("member_id")
                row["TULOY ID"] = "" if tuloy_id is None else str(tuloy_id)
                row["MEMBER ID"] = "" if member_id is None else str(member_id)
                row["IMPORT ERROR"] = ""
                v_succ = 1
            except (ApiRequestError, RequestTimeout, RuntimeError, ValueError, KeyError) as error:
                row["IMPORT ERROR"] = f"Verification failed: {error}"
                fail = 1
                return v_succ, p_succ, fail

        # Posting Step
        if args.verify_only:
            return v_succ, p_succ, fail
        if (row.get("TESDA POST STATUS") or "").strip() == "SUCCESS":
            return v_succ, p_succ, fail
        if not (row.get("VERIFY STATUS") or "").strip():
            return v_succ, p_succ, fail

        try:
            payload = tesda_payload(row)
            client.post_json("/PostEnrolleeMatchedTESDA", payload)
            row["TESDA POST STATUS"] = "SUCCESS"
            row["IMPORT ERROR"] = ""
            p_succ = 1
        except (ApiRequestError, RequestTimeout, RuntimeError, ValueError, KeyError) as error:
            row["TESDA POST STATUS"] = "FAILED"
            row["IMPORT ERROR"] = f"TESDA submission failed: {error}"
            fail = 1

    except Exception as e:
        row["IMPORT ERROR"] = f"Unexpected error: {e}"
        fail = 1

    return v_succ, p_succ, fail

def _process_and_write_chunk(chunk, client, args, writer, target_file, pbar, stats):
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_row_task, r, client, args) for r in chunk]
        
        for future in concurrent.futures.as_completed(futures):
            v_succ, p_succ, fail = future.result()
            stats["verify_successes"] += v_succ
            stats["post_successes"] += p_succ
            stats["failures"] += fail
            
            pbar.set_postfix({
                "Verified": stats["verify_successes"], 
                "Posted": stats["post_successes"], 
                "Errors": stats["failures"]
            })
            pbar.update(1)
            
    # Rows were modified in-place concurrently; write them in original sequential order
    for row in chunk:
        writer.writerow(row)

    target_file.flush()
    os.fsync(target_file.fileno())

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Verify TESDA CSV records and submit them through the Tuloy API."
    )
    parser.add_argument("--csv", required=True, help="CSV file to process")
    parser.add_argument(
        "--base-url",
        default=os.getenv("TULOY_API_BASE_URL"),
        help="API root URL (defaults to TULOY_API_BASE_URL in the project .env)",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("TULOY_API_USERNAME"),
        help="API username (or set TULOY_API_USERNAME)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("TULOY_API_PASSWORD"),
        help="API password (or set TULOY_API_PASSWORD)",
    )
    parser.add_argument("--timeout", type=float, default=30, help="Request timeout in seconds")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only call VerifyMemberBene and save the IDs/statuses to the CSV",
    )
    parser.add_argument(
        "--reverify",
        action="store_true",
        help="Re-run verification even when the CSV already has a VERIFY STATUS",
    )
    args = parser.parse_args(argv)

    try:
        if not args.base_url:
            raise RuntimeError(
                "Set TULOY_API_BASE_URL in the project .env file, "
                "or pass --base-url."
            )
        if args.timeout <= 0:
            raise ValueError("--timeout must be greater than zero")

        if not os.path.exists(args.csv):
            print(f"CSV file {args.csv} not found.")
            return 1

        # 1. Count total rows in the source CSV (fast pass)
        with open(args.csv, "r", encoding="utf-8-sig") as f:
            total_rows = sum(1 for _ in f) - 1 # Subtract header
            
        if total_rows <= 0:
            print("CSV contains no data rows.")
            return 0

        # 2. Check for temporary progress file
        temp_csv = args.csv + ".tmp"
        processed_count = 0
        if os.path.exists(temp_csv):
            with open(temp_csv, "r", encoding="utf-8-sig") as f:
                processed_count = sum(1 for _ in f) - 1
            if processed_count < 0:
                processed_count = 0
                
        if processed_count >= total_rows:
            print("All rows already processed. Finalizing file replacement...")
            os.replace(temp_csv, args.csv)
            return 0

        client = ApiClient(args.base_url, args.username, args.password, args.timeout)
        stats = {"verify_successes": 0, "post_successes": 0, "failures": 0}
        CHUNK_SIZE = 10000

        # 3. Stream processing
        with open(args.csv, "r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames:
                raise ValueError("CSV file is empty or has no header row")
                
            missing = [
                column
                for column in ("FIRST NAME", "LAST NAME", "BIRTHDATE")
                if column not in reader.fieldnames
            ]
            if missing:
                raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")
                
            fieldnames = list(reader.fieldnames)
            for column in CHECKPOINT_COLUMNS:
                if column not in fieldnames:
                    fieldnames.append(column)
                    
            mode = "a" if processed_count > 0 else "w"
            with open(temp_csv, mode, encoding="utf-8-sig", newline="") as target:
                writer = csv.DictWriter(target, fieldnames=fieldnames, extrasaction="ignore")
                if mode == "w":
                    writer.writeheader()
                    
                # Skip already processed rows
                for _ in range(processed_count):
                    try:
                        next(reader)
                    except StopIteration:
                        break
                        
                chunk = []
                pbar = tqdm(total=total_rows, initial=processed_count, desc="Processing CSV rows", unit="row")
                
                # Stream row by row
                for row in reader:
                    chunk.append(row)
                    if len(chunk) >= CHUNK_SIZE:
                        _process_and_write_chunk(chunk, client, args, writer, target, pbar, stats)
                        chunk = []
                        
                if chunk:
                    _process_and_write_chunk(chunk, client, args, writer, target, pbar, stats)
                    
                pbar.close()

        # 4. Atomic file replacement
        for attempt in range(5):
            try:
                os.replace(temp_csv, args.csv)
                break
            except PermissionError as error:
                if attempt < 4:
                    time.sleep(0.25 * (2**attempt))
                    continue
                winerror = getattr(error, "winerror", None)
                windows_error = f" Windows error {winerror}." if winerror else ""
                raise RuntimeError(
                    f"Processing complete, but cannot update CSV checkpoint '{args.csv}'. "
                    f"{windows_error} Close any preview/editor preventing replacement."
                ) from error

        print(
            f"Finished. Verified: {stats['verify_successes']}; "
            f"TESDA submissions: {stats['post_successes']}; failures: {stats['failures']}."
        )
        return 1 if stats['failures'] else 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Import aborted: {error}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
