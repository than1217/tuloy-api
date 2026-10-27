# User Match API

This project is a FastAPI application that provides secure authentication and an endpoint to match user/beneficiary data against a MySQL database. It takes a user's first name, last name, and date of birth, generates an MD5 hash from this information, and then queries a database to find matching records. Optional identity fields can further narrow the search.

## Features

-   **User Matching**: Matches user data based on a generated MD5 hash and optional identity filters.
-   **Match Status Handling**: Returns standard statuses: "Not Found", "Multiple Match Found", and "Matched".
-   **Authentication & Security**: JWT-based OAuth2 authentication (signup, token generation, and route protection using bcrypt for password hashing).
-   **Response Caching**: Caching on `GET /GetEligibleBene` via `fastapi-cache2` with Redis support and automatic in-memory fallback.
-   **SSH Tunnel Support**: Connects to remote databases located behind an SSH bastion/jump server.
-   **Environment Configuration**: Configured using environment variables (`.env`).

## Requirements

-   Python 3.8+
-   A MySQL database

## Project Structure

The codebase is organized modularly:
- **`main.py`**: Application entrypoint and startup configuration.
- **`database.py`**: MySQL database connection and SSH tunnel logic.
- **`schemas.py`**: Pydantic models for request validation.
- **`security.py`**: JWT generation and password hashing.
- **`utils.py`**: Helper functions (e.g., MD5 hashing, cache key builder).
- **`routers/`**: Contains the API route definitions (`auth.py` and `beneficiaries.py`).

## Installation

1.  **Clone the repository or download the project files.**

2.  **Create and activate a virtual environment:**

    ```bash
    python -m venv venv
    # On Windows (PowerShell)
    .\venv\Scripts\Activate.ps1
    # On Windows (CMD)
    .\venv\Scripts\activate.bat
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install the required dependencies:**

    Ensure your virtual environment is activated, then run:

    ```bash
    pip install -r requirements.txt
    ```
    *(Alternatively, you can run `.\venv\Scripts\pip install -r requirements.txt` on Windows to guarantee the packages are installed locally in the virtual environment.)*

4.  **Configure your environment variables:**

    Create a file named `.env` in the project root and configure your database and authentication details:

    ```env
    DB_HOST=localhost
    DB_PORT=3306
    DB_DATABASE=your_database_name
    DB_USER=your_username
    DB_PASSWORD=your_password

    # Authentication (Optional overrides)
    SECRET_KEY=your-super-secret-key-for-jwt
    ACCESS_TOKEN_EXPIRE_MINUTES=30

    # Optional: Caching (defaults to redis://localhost:6379 with InMemory fallback, 1200s TTL)
    REDIS_URL=redis://localhost:6379
    CACHE_EXPIRE_SECONDS=1200

    # Optional: SSH Tunneling (if database is behind a jump host)
    SSH_HOST=your_ssh_host
    SSH_PORT=22
    SSH_USER=your_ssh_username
    SSH_PASSWORD=your_ssh_password
    # SSH_PKEY=/path/to/private/key
    ```
    *(Note: `SSH_PASSWORD` or `SSH_PKEY` is required if `SSH_HOST` is set. The API automatically tests the SSH tunnel and database connection upon startup).*

## Database Setup

Before running the application, ensure your database has:

1.  A source view or table named `vw_verify_member_bene` that the API can query against.
2.  An `api_users` table for authentication, along with `matching_transaction_CHED_tbl` and `enroll_matched_CHED_tbl` for tracking CHED responses (all created automatically during application startup if the database user has `CREATE TABLE` permissions):

    ```sql
    CREATE TABLE IF NOT EXISTS api_users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) UNIQUE NOT NULL,
        hashed_password VARCHAR(255) NOT NULL,
        disabled BOOLEAN DEFAULT FALSE
    );
    -- (The schema for the matching and enrollment tables are also initialized automatically on startup)
    ```

## Usage

To run the application, simply execute the `main.py` script:

```bash
python main.py
```

The API will attempt to bind to your local IP address on port 80 (e.g., `http://192.168.x.x`). If it cannot determine a local IP, it will fall back to `http://127.0.0.1`.

## Interactive API Documentation

FastAPI provides built-in interactive Swagger documentation:

1.  Start the application.
2.  Open your browser and navigate to the IP address printed in the terminal (e.g. `http://192.168.x.x/docs` or `http://127.0.0.1/docs`).
3.  Use the `Authorize` button at the top right to log in and test protected routes.

---

## API Endpoints

### 1. `POST /signup`
Registers a new API user.

**Request Body:**
```json
{
  "username": "api_user",
  "password": "StrongPassword123"
}
```

**Responses:**
- `201 Created`: User registered successfully.
- `400 Bad Request`: Username already registered.

---

### 2. `POST /token`
Authenticates user credentials and returns an access and refresh token (OAuth2 password flow).

**Request (Form Data / `application/x-www-form-urlencoded`):**
- `username`: api_user
- `password`: StrongPassword123

**Response:**
```json
{
  "access_token": "your_access_token",
  "refresh_token": "your_refresh_token",
  "token_type": "bearer"
}
```

---

### 3. `POST /refresh`
Generates a new access token using a valid refresh token.

**Request Body:**
```json
{
  "refresh_token": "your_refresh_token"
}
```

**Response:**
```json
{
  "access_token": "your_new_access_token",
  "token_type": "bearer"
}
```

---

### 4. `POST /VerifyMemberBene`
*(Requires Bearer Token authentication)*

Receives user details, computes an MD5 hash, and queries `vw_verify_member_bene`.

**Headers:**
```http
Authorization: Bearer <your_access_token>
Content-Type: application/json
```

**Request Body:**

```json
{
  "first_name": "John",
  "middle_name": "Quincy",
  "last_name": "Doe",
  "date_of_birth": "1990-01-15",
  "sex": "Male",
  "member_id": "123456",
  "household_id": "789012",
  "lrn": "100000000001",
  "pcn": "1234567890123456",
  "geocode": "123456789"
}
```

- **Required Fields:** `first_name`, `last_name`, `date_of_birth`
- **Optional Fields:** `middle_name`, `sex`, `member_id`, `household_id`, `lrn`, `pcn`, `geocode` (used as exact-match filters; `sex` maps to `sex_id`, `household_id` to `listahanan_id`, `pcn` to `philsys`, and `geocode` to `bgy_psgc_code` in `vw_verify_member_bene`).

**Responses:**

- **`200 OK` - Not Found:**
  ```json
  {
    "status": "Not Found",
    "tuloy_id": null,
    "member_id": null
  }
  ```
- **`200 OK` - Multiple Matches:**
  ```json
  {
    "status": "Multiple Match Found",
    "tuloy_id": null,
    "member_id": null
  }
  ```
- **`200 OK` - Matched:**
  ```json
  {
    "status": "Matched",
    "tuloy_id": "123456",
    "member_id": 789012
  }
  ```
  `tuloy_id` and `member_id` are taken from the uniquely matched database record. They are `null` when there is no match or multiple records match.
- **`401 Unauthorized`:** Missing, invalid, or expired Bearer token.
- **`500 Internal Server Error`:** Database connection or query execution failure.

---

### 5. `GET /GetEligibleBene`
*(Requires ****** authentication)*

Returns one page of records from `vw_verify_member_bene` to avoid loading the entire dataset into memory or sending millions of rows in one response.

**Query parameters:**
- `limit` (optional, default `100`, maximum `1000`): Number of records to return.
- `offset` (optional, default `0`): Number of records to skip before returning the page.

**Headers:**
```http
Authorization: ******
```

**Response:**
```json
{
  "items": [],
  "limit": 100,
  "offset": 0,
  "has_more": true,
  "next_offset": 100
}
```
Use `next_offset` as the `offset` for the next request while `has_more` is `true`. The endpoint does not calculate a total count, avoiding an additional potentially expensive query.

**Responses:**
- **`200 OK`:** One page of eligible beneficiary records and pagination metadata.
- **`401 Unauthorized`:** Missing, invalid, or expired ******
- **`500 Internal Server Error`:** Database connection or query execution failure.

---

### 6. `POST /PostEnrolleeMatchedCHED`
*(Requires ****** authentication)*

Receives CHED match data payload and persists it to the `matching_transaction_CHED_tbl` and `enroll_matched_CHED_tbl` tables.

**Headers:**
```http
Authorization: ******
Content-Type: application/json
```

**Request Body:**
```json
{
  "status": true,
  "message": "FOUND",
  "enrollment_id": 1,
  "data": {
    "id": "4ps-1234",
    "member_id": 1234,
    "student_id": 12345,
    "mothers_maiden": {
      "first_name": "JUANA",
      "middle_name": "",
      "last_name": "MARIA"
    },
    "degree": {
      "program_name": "BS IT",
      "date_enrolled": "2026-08-01",
      "program_duration": 4,
      "academic_year": "2026-2027",
      "year_level": 1,
      "semester": 1
    },
    "enrollment_status": "ENROLLED",
    "date_encoded": "2026-10-23",
    "date_updated": null
  },
  "error_code": null
}
```

**Responses:**
- **`200 OK`:** 
  ```json
  {
    "message": "CHED response recorded successfully."
  }
  ```
- **`401 Unauthorized`:** Missing, invalid, or expired ******
- **`500 Internal Server Error`:** Database connection or query execution failure.

---

### 7. `GET /GetMatchedChedBene`
*(Requires ****** authentication)*

Returns paginated records directly from the `enroll_matched_CHED_tbl` table containing the imported CHED matches.

**Query parameters:**
- `limit` (optional, default `100`, maximum `1000`): Number of records to return.
- `offset` (optional, default `0`): Number of records to skip before returning the page.

**Headers:**
```http
Authorization: ******
```

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "match_id": 1,
      "enrollment_id": 0,
      "tuloy_id": "4ps-33082079",
      "member_id": 33082079,
      "student_id": "0",
      "mm_first_name": "LOIDA",
      "mm_middle_name": "",
      "mm_last_name": "AMURAO",
      "degree_program_name": "BACHELOR OF SCIENCE IN BUSINESS ADMINISTRATION MAJOR IN MARKETING MANAGEMENT",
      "degree_date_enrolled": null,
      "degree_program_duration": null,
      "degree_academic_year": "2026-2027",
      "degree_year_level": 3,
      "degree_semester": 1,
      "enrollment_status": "ENROLLED",
      "date_encoded": null,
      "date_updated": null,
      "created_at": "2026-10-23T10:00:00",
      "updated_at": null
    }
  ],
  "limit": 100,
  "offset": 0,
  "has_more": false,
  "next_offset": null
}
```

---

### 8. `POST /PostEnrolleeMatchedTESDA`
*(Requires ****** authentication)*

Receives TESDA match data payload and persists it to the `matching_transaction_TESDA_tbl` and `enroll_matched_TESDA_tbl` tables.

**Headers:**
```http
Authorization: ******
Content-Type: application/json
```

**Request Body:**
```json
{
  "status": true,
  "message": "FOUND",
  "data": {
    "id": "4ps-1234",
    "member_id": 1234,
    "uli": 123456,
    "mothers_maiden": {
      "first_name": "JUANA",
      "middle_name": "",
      "last_name": "MARIA"
    },
    "diploma": {
      "program_name": "",
      "date_enrolled": "",
      "program_duration": 4,
      "academic_year": "2026-2027",
      "year_level": 1,
      "semester": 1
    },
    "short_course": {
      "program_name": "",
      "start_date": "",
      "end_date": "",
      "training_status": ""
    },
    "enrollment_status": "",
    "date_encoded": "",
    "date_updated": ""
  },
  "error_code": null
}
```

**Responses:**
- **`200 OK`:** 
  ```json
  {
    "message": "TESDA response recorded successfully."
  }
  ```
- **`401 Unauthorized`:** Missing, invalid, or expired ******
- **`500 Internal Server Error`:** Database connection or query execution failure.

---

### 9. `GET /GetMatchedTesdaBene`
*(Requires ****** authentication)*

Returns paginated records directly from the `enroll_matched_TESDA_tbl` table containing the imported TESDA matches.

**Query parameters:**
- `limit` (optional, default `100`, maximum `1000`): Number of records to return.
- `offset` (optional, default `0`): Number of records to skip before returning the page.

**Headers:**
```http
Authorization: ******
```

**Response:**
```json
{
  "items": [
    {
      "id": 1,
      "match_id": 1,
      "enrollment_id": 0,
      "tuloy_id": "4ps-33082079",
      "member_id": 33082079,
      "uli_id": "123456",
      "mm_first_name": "LOIDA",
      "mm_middle_name": "",
      "mm_last_name": "AMURAO",
      "diploma": {
        "program_name": "BS IT",
        "date_enrolled": "2026-08-01",
        "program_duration": 4,
        "academic_year": "2026-2027",
        "year_level": 1,
        "semester": 1,
        "enrollment_status": "ENROLLED"
      },
      "short_course": {
        "program_name": "",
        "start_date": "",
        "end_date": "",
        "training_status": ""
      },
      "date_encoded": null,
      "date_updated": null,
      "created_at": "2026-10-23T10:00:00",
      "updated_at": null
    }
  ],
  "limit": 100,
  "offset": 0,
  "has_more": false,
  "next_offset": null
}
```

---

## Testing with cURL

1. **Sign up:**
   ```bash
   curl -X POST "http://127.0.0.1:8000/signup" \
     -H "Content-Type: application/json" \
     -d '{"username": "testuser", "password": "password123"}'
   ```

2. **Obtain Access Token:**
   ```bash
   curl -X POST "http://127.0.0.1:8000/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=testuser&password=password123"
   ```

3. **Verify Member (with Bearer Token):**
   ```bash
   curl -X POST "http://127.0.0.1:8000/VerifyMemberBene" \
     -H "Authorization: Bearer <access_token>" \
     -H "Content-Type: application/json" \
     -d '{
       "first_name": "John",
       "last_name": "Doe",
       "date_of_birth": "1990-01-15"
     }'
   ```

---

## Bulk Data Import (CHED Matches)

The project includes multi-threaded Python scripts to process a bulk CSV of CHED matching results and automatically POST them into the API.

1. Ensure the API is running locally (uvicorn main:app).
2. In a separate terminal, run the test script (samples 10 rows) or the full import script:
   `ash
   # Test with 10 rows
   .\venv\Scripts\python.exe others\test_import_ched_csv.py
   
   # Run the full import script (reads chunks of 10,000 rows, 5 parallel workers)
   .\venv\Scripts\python.exe others\import_ched_csv.py
   `
   *(Note: The scripts will automatically sign up / log in as dmin to fetch a JWT token for the API requests, and will dynamically resolve the CHED-Matching.csv location).*

