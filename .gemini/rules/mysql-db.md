# MySQL Database Rules

## Connection Management
- Connections are provided via the `get_db_connection` FastAPI dependency located in `app.db.database`.
- Always use the dependency (`db = Depends(get_db_connection)`); do not connect manually inside routes.
- Ensure cursors are properly closed, ideally using `try...finally` blocks.

## Queries
- Use parameterized queries (`%s`) to prevent SQL injection.
- Do NOT use string interpolation (f-strings) for SQL variables.
- When selecting data, consider using `cursor = db.cursor(dictionary=True)` for easier Pydantic serialization.
