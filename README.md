# User Match API

This project is a simple FastAPI application that provides an endpoint to match user data against a database. It takes a user's first name, last name, and date of birth, generates an MD5 hash from this information, and then queries a database to find a matching record.

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
    DB_DATABASE=your_database_name
    DB_USER=your_username
    DB_PASSWORD=your_password
    ```

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
  "last_name": "Doe",
  "date_of_birth": "1990-01-15"
}
```

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
