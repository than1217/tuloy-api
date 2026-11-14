# FastAPI Setup & Architecture

## Context
This project `tuloy-api` is a FastAPI web application.

## Directory Structure
- `app/main.py`: Entry point and application setup (including DB/SSH tunnel lifecycle).
- `app/api/routes/`: Contains all route handlers (APIRouter).
- `app/core/`: Security and logging configuration.
- `app/db/`: Database configuration and connection dependencies.
- `app/schemas/`: Pydantic models for validation.

## Principles
- Use explicit dependencies (like `Depends(get_db_connection)`).
- Never place DB connections in global state. Always use FastAPI's dependency injection.
- Keep route handlers thin; delegate complex logic to service functions or keep simple logic inline if it's purely SQL querying.
