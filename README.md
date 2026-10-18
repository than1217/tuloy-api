# User Match API

This project is a simple FastAPI application that provides an endpoint to match user data against a database. It takes a user's first name, last name, and date of birth, generates an MD5 hash from this information, and then queries a database to find a matching record. Optional identity fields can further narrow the search.

## Features

-   Matches user data based on a generated hash.
-   Handles cases for "Not Found", "Multiple Match Found", and "Matched".
-   Uses environment variables for secure database configuration.

## Requirements

-   Python 3.7+
-   A MySQL database

## Installation

1.  **Clone the repository or download the project files.**

2.  **Create and activate a virtual environment:**

    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install the required dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure your environment variables:**

    Create a file named `.env` in the project root and add your database connection details. An example is provided in `.env.example`.

    ```env
    DB_HOST=localhost
    DB_PORT=3306
    DB_DATABASE=your_database_name
    DB_USER=your_username
    DB_PASSWORD=your_password
    ```

    **Optional: SSH Tunneling**
    If your database is behind a jump server, you can configure an SSH tunnel by providing the following variables:
    ```env
    SSH_HOST=your_ssh_host
    SSH_PORT=22
    SSH_USER=your_ssh_username
    SSH_PASSWORD=your_ssh_password
    SSH_PKEY=/path/to/private/key
    ```
    (Note: `SSH_PASSWORD` or `SSH_PKEY` is required if `SSH_HOST` is set.)

## Database Setup

Before running the application, ensure your database is set up with the necessary tables. You will need:

1.  A source view or table (e.g., `vw_verify_member_bene`) that the API can query against.

## Usage

To run the application, use `uvicorn`:

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Testing

The easiest way to test the endpoint is to use the interactive API documentation provided by FastAPI.

1.  Run the application.
2.  Open your browser and navigate to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
3.  Click on the `/VerifyMemberBene` endpoint, click "Try it out", and execute a test request.

You can also use an API client like Postman or the following `curl` command:

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/VerifyMemberBene' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "first_name": "John",
  "last_name": "Doe",
  "date_of_birth": "1990-01-15"
}'
```

## API Endpoint

### `POST /VerifyMemberBene`

This endpoint receives user details, generates a hash, and attempts to find a match in the database.

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

`first_name`, `last_name`, and `date_of_birth` are required. `middle_name`, `sex`, `member_id`, `household_id`, `lrn`, `pcn`, and `geocode` are optional; when provided, each is used as an exact-match filter against the corresponding column in `vw_verify_member_bene`.

**Responses:**

-   **`200 OK` - Not Found:**
    ```json
    {
      "status": "Not Found",
      "md5_hash": "..."
    }
    ```
-   **`200 OK` - Multiple Matches:**
    ```json
    {
      "status": "Multiple Match Found",
      "md5_hash": "..."
    }
    ```
-   **`200 OK` - Matched:**
    ```json
    {
      "status": "Matched",
      "md5_hash": "..."
    }
    ```
-   **`500 Internal Server Error`:** Indicates a database connection or query error.
