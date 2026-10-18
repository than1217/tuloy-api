# User Match API

This project is a FastAPI application that provides secure authentication and an endpoint to match user/beneficiary data against a MySQL database. It takes a user's first name, last name, and date of birth, generates an MD5 hash from this information, and then queries a database to find matching records. Optional identity fields can further narrow the search.

## Features

-   **User Matching**: Matches user data based on a generated MD5 hash and optional identity filters.
-   **Match Status Handling**: Returns standard statuses: "Not Found", "Multiple Match Found", and "Matched".
-   **Authentication & Security**: JWT-based OAuth2 authentication (signup, token generation, and route protection using bcrypt for password hashing).
-   **SSH Tunnel Support**: Connects to remote databases located behind an SSH bastion/jump server.
-   **Environment Configuration**: Configured using environment variables (`.env`).

## Requirements

-   Python 3.8+
-   A MySQL database

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

    ```bash
    pip install -r requirements.txt
    ```

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
2.  An `api_users` table for authentication (created automatically during application startup if the database user has `CREATE TABLE` permissions):

    ```sql
    CREATE TABLE IF NOT EXISTS api_users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) UNIQUE NOT NULL,
        hashed_password VARCHAR(255) NOT NULL,
        disabled BOOLEAN DEFAULT FALSE
    );
    ```

## Usage

To run the application, use `uvicorn`:

```bash
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`.

## Interactive API Documentation

FastAPI provides built-in interactive Swagger documentation:

1.  Start the application.
2.  Open your browser and navigate to [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).
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
Authenticates user credentials and returns a Bearer access token (OAuth2 password flow).

**Request (Form Data / `application/x-www-form-urlencoded`):**
- `username`: api_user
- `password`: StrongPassword123

**Response:**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer"
}
```

---

### 3. `POST /VerifyMemberBene`
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
- **Optional Fields:** `middle_name`, `sex`, `member_id`, `household_id`, `lrn`, `pcn`, `geocode` (used as exact-match filters against the corresponding table columns).

**Responses:**

- **`200 OK` - Not Found:**
  ```json
  {
    "status": "Not Found",
    "md5_hash": "b10a8db164e0754105b7a99be72e3fe5"
  }
  ```
- **`200 OK` - Multiple Matches:**
  ```json
  {
    "status": "Multiple Match Found",
    "md5_hash": "b10a8db164e0754105b7a99be72e3fe5"
  }
  ```
- **`200 OK` - Matched:**
  ```json
  {
    "status": "Matched",
    "md5_hash": "b10a8db164e0754105b7a99be72e3fe5"
  }
  ```
- **`401 Unauthorized`:** Missing, invalid, or expired Bearer token.
- **`500 Internal Server Error`:** Database connection or query execution failure.

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
