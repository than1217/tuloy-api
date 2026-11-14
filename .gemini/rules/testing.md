# API Testing Rules

## Testing Framework
- Tests are written using `pytest` and `pytest-asyncio` for async tests.
- Use `httpx.AsyncClient` or FastAPI's `TestClient` for endpoint testing.

## Database Testing
- Do not run tests against the production database.
- Use mocked dependencies (`app.dependency_overrides[get_db_connection]`) to provide a mock database connection during testing.
