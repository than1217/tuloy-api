import argparse
import concurrent.futures
import csv
import json
import os
import sys
import threading
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
load_dotenv(dotenv_path=os.path.join(PROJECT_DIR, ".env"), override=True)

REQUIRED_CSV_COLUMNS = {
    "Degree Program",
    "Year level",
    "Academic Year",
}
VERIFY_STATUS_VALUES = {"Matched", "Not Found", "Multiple Match Found"}


class ApiRequestError(RuntimeError):
    pass


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
            headers["Authorization"] = f"Bearer {request_token}"

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
            raise RuntimeError(
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
            raise RuntimeError(
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
    first_name = (row.get("First name") or row.get("MEMBER First name") or "").strip()
    last_name = (row.get("Last name") or row.get("MEMBER Last name") or "").strip()
    birthdate = (row.get("Birthdate") or row.get("Birthday") or "").strip()
    if not first_name or not last_name or not birthdate:
        raise ValueError("First name, Last name, and Birthdate are required")

    for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            birthdate = datetime.strptime(birthdate, date_format).date().isoformat()
            break
        except ValueError:
            continue
    else:
        raise ValueError(f"Invalid Birthdate: {birthdate!r}")

    return {
        "first_name": first_name,
        "last_name": last_name,
        "date_of_birth": birthdate,
    }


def ched_payload(row, verification):
    status = verification.get("status")
    if status not in VERIFY_STATUS_VALUES:
        raise ValueError(f"Unexpected verification response: {verification!r}")
    is_match = status == "Matched"

    try:
        year_level = int(row.get("Year level", 0))
    except (TypeError, ValueError):
        year_level = 0

    data = None
    if is_match:
        tuloy_id = verification.get("tuloy_id")
        if not tuloy_id or len(str(tuloy_id)) > 50:
            raise ValueError("Verification returned an invalid TULOY ID")
        try:
            member_id = int(verification["member_id"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Verification returned an invalid MEMBER ID") from error
        if not 1 <= member_id <= 4294967295:
            raise ValueError("Verification returned an invalid MEMBER ID")

        data = {
            "id": str(tuloy_id),
            "member_id": member_id,
            "student_id": 0,
            "mothers_maiden": None,
            "degree": {
                "program_name": row.get("Degree Program", ""),
                "date_enrolled": None,
                "program_duration": None,
                "academic_year": row.get("Academic Year", ""),
                "year_level": year_level if year_level > 0 else None,
                "semester": 1,
            },
            "enrollment_status": "ENROLLED",
            "date_encoded": None,
            "date_updated": None,
        }

    return {
        "status": is_match,
        "message": "FOUND" if is_match else status.upper(),
        "enrollment_id": 0,
        "data": data,
        "error_code": None,
    }


def process_row(row, client):
    row_id = row.get("id", "?")
    try:
        verification = client.post_json("/VerifyMemberBene", verify_payload(row))
        payload = ched_payload(row, verification)
        client.post_json("/PostEnrolleeMatchedCHED", payload)
    except (ApiRequestError, ValueError, KeyError) as error:
        print(f"Failed to process CSV row {row_id}: {error}")
        return False
    return True


def process_chunk(chunk, client, chunk_index):
    success_count = 0
    print(f"[Chunk {chunk_index}] Starting chunk of {len(chunk)} rows...")

    for index, row in enumerate(chunk):
        if process_row(row, client):
            success_count += 1

        if (index + 1) % 1000 == 0:
            print(f"[Chunk {chunk_index}] Progress: {index + 1} / {len(chunk)} processed")

    print(f"[Chunk {chunk_index}] Completed. Success: {success_count} / {len(chunk)}")
    return success_count


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import CHED CSV data via API.")
    parser.add_argument("--csv", required=True, help="Path to the CSV file to import")
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
            raise FileNotFoundError(f"CSV file {args.csv} not found.")

        chunks = []
        current_chunk = []
        with open(args.csv, "r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            if not reader.fieldnames:
                raise ValueError("CSV file is empty or has no header row.")
            missing_columns = sorted(REQUIRED_CSV_COLUMNS - set(reader.fieldnames))
            if missing_columns:
                raise ValueError(
                    "CSV is missing required columns: "
                    f"{', '.join(missing_columns)}."
                )
            header = set(reader.fieldnames)
            has_raw_names = {"First name", "Last name", "Birthdate"} <= header
            has_enriched_names = {
                "MEMBER First name",
                "MEMBER Last name",
                "Birthday",
            } <= header
            if not has_raw_names and not has_enriched_names:
                raise ValueError(
                    "CSV must include First name, Last name, and Birthdate "
                    "(or the corresponding MEMBER First name, MEMBER Last name, "
                    "and Birthday columns)."
                )
            for row in reader:
                current_chunk.append(row)
                if len(current_chunk) == 10000:
                    chunks.append(current_chunk)
                    current_chunk = []
        if current_chunk:
            chunks.append(current_chunk)

        total_rows = sum(len(chunk) for chunk in chunks)
        if not total_rows:
            print("CSV contains no data rows.")
            return 0

        client = ApiClient(args.base_url, args.username, args.password, args.timeout)
        print(
            f"Loaded {total_rows} rows into {len(chunks)} chunks of up to "
            "10,000 rows. Processing with 5 workers..."
        )
        total_success = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(process_chunk, chunk, client, index): index
                for index, chunk in enumerate(chunks, 1)
            }
            for future in concurrent.futures.as_completed(futures):
                try:
                    total_success += future.result()
                except (RuntimeError, ValueError, KeyError) as error:
                    index = futures[future]
                    print(f"[Chunk {index}] Failed with exception: {error}")

        print(f"Done! Successfully imported {total_success} out of {total_rows} rows.")
        return 0 if total_success == total_rows else 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Import aborted: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
