import argparse
import csv
import json
import os
import sys
import tempfile
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from dotenv import load_dotenv
from tqdm import tqdm

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
load_dotenv(dotenv_path=os.path.join(PROJECT_DIR, ".env"), override=True)

DEFAULT_CSV = os.path.join(SCRIPT_DIR, "TESDA Matching 136.csv")
CHECKPOINT_COLUMNS = (
    "TULOY ID",
    "MEMBER ID",
    "VERIFY STATUS",
    "TESDA POST STATUS",
    "IMPORT ERROR",
)


class RequestTimeout(RuntimeError):
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

    def _request(self, path, body, content_type, authenticated=True, retry_auth=True):
        headers = {"Content-Type": content_type}
        if authenticated:
            if not self.access_token:
                self.login()
            headers["Authorization"] = f"Bearer {self.access_token}"

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
                self.refresh()
                return self._request(path, body, content_type, retry_auth=False)
            raise RuntimeError(
                f"POST {path} failed with HTTP {error.code}: {response_body}"
            ) from error
        except TimeoutError as error:
            raise RequestTimeout(
                f"POST {path} timed out after {self.timeout:g} seconds"
            ) from error
        except URLError as error:
            raise RuntimeError(f"Could not reach {self.base_url}: {error.reason}") from error

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
                self.access_token = read_json_response(response)["access_token"]
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


def save_csv(path, fieldnames, rows):
    directory = os.path.dirname(os.path.abspath(path))
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            dir=directory,
            delete=False,
        ) as output:
            temporary_path = output.name
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary_path, path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


def load_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as source:
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
        rows = list(reader)
    return fieldnames, rows


def main():
    parser = argparse.ArgumentParser(
        description="Verify TESDA CSV records and submit them through the Tuloy API."
    )
    parser.add_argument("--csv", default=DEFAULT_CSV, help="CSV file to process")
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
    args = parser.parse_args()

    try:
        if not args.base_url:
            raise RuntimeError(
                "Set TULOY_API_BASE_URL in the project .env file, "
                "or pass --base-url."
            )

        fieldnames, rows = load_csv(args.csv)
        if not rows:
            print("CSV contains no data rows.")
            return 0

        client = ApiClient(args.base_url, args.username, args.password, args.timeout)
        verify_successes = 0
        post_successes = 0
        failures = 0

        # Set up the progress bar
        pbar = tqdm(rows, desc="Processing CSV rows", unit="row")

        for index, row in enumerate(pbar, start=2):
            if row.get(None):
                raise ValueError(f"CSV row {index} has more fields than the header")

            # Update progress bar description to show current status
            pbar.set_postfix({"Verified": verify_successes, "Posted": post_successes, "Errors": failures})

            if args.reverify or not (row.get("VERIFY STATUS") or "").strip():
                if args.reverify:
                    row["VERIFY STATUS"] = ""
                    row["TULOY ID"] = ""
                    row["MEMBER ID"] = ""
                    row["TESDA POST STATUS"] = ""
                try:
                    result = client.post_json(
                        "/VerifyMemberBene", verify_payload(row)
                    )
                    status = result.get("status")
                    if status not in ("Matched", "Not Found", "Multiple Match Found"):
                        raise RuntimeError(f"Unexpected verification response: {result!r}")
                    if status == "Matched" and (
                        result.get("tuloy_id") is None or result.get("member_id") is None
                    ):
                        raise RuntimeError(
                            "Verification returned Matched without both IDs"
                        )
                    row["VERIFY STATUS"] = status
                    tuloy_id = result.get("tuloy_id")
                    member_id = result.get("member_id")
                    row["TULOY ID"] = "" if tuloy_id is None else str(tuloy_id)
                    row["MEMBER ID"] = "" if member_id is None else str(member_id)
                    row["IMPORT ERROR"] = ""
                    verify_successes += 1
                    save_csv(args.csv, fieldnames, rows)
                except RequestTimeout:
                    raise
                except (RuntimeError, ValueError, KeyError) as error:
                    row["IMPORT ERROR"] = f"Verification failed: {error}"
                    failures += 1
                    save_csv(args.csv, fieldnames, rows)
                    tqdm.write(f"Row {index}: {row['IMPORT ERROR']}")
                    continue

            if args.verify_only:
                continue
            if (row.get("TESDA POST STATUS") or "").strip() == "SUCCESS":
                continue
            if not (row.get("VERIFY STATUS") or "").strip():
                continue

            try:
                payload = tesda_payload(row)
                client.post_json("/PostEnrolleeMatchedTESDA", payload)
                row["TESDA POST STATUS"] = "SUCCESS"
                row["IMPORT ERROR"] = ""
                post_successes += 1
            except RequestTimeout:
                raise
            except (RuntimeError, ValueError, KeyError) as error:
                row["TESDA POST STATUS"] = "FAILED"
                row["IMPORT ERROR"] = f"TESDA submission failed: {error}"
                failures += 1
                tqdm.write(f"Row {index}: {row['IMPORT ERROR']}")
            save_csv(args.csv, fieldnames, rows)

        # Ensure final update to progress bar postfix before closing
        pbar.set_postfix({"Verified": verify_successes, "Posted": post_successes, "Errors": failures})
        pbar.close()

        print(
            f"Finished. Verified: {verify_successes}; "
            f"TESDA submissions: {post_successes}; failures: {failures}."
        )
        return 1 if failures else 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Import aborted: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
