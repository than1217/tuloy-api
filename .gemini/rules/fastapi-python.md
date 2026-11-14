# FastAPI & Python Rules

## Types & Validation
- Utilize modern Python typing features.
- Pydantic v2 schemas should be used for request and response validation.
- All endpoints must include type hints for request bodies, query parameters, and dependencies.

## Asynchronous vs Synchronous
- The application uses `mysql-connector-python`, which is synchronous.
- Database calls must be done in standard `def` endpoints (not `async def`) UNLESS properly offloaded. If you declare an endpoint as `async def` and use a synchronous DB call inside, it will block the event loop and crash the concurrency.
- Caching with `fastapi-cache2` uses `aioredis`, which is asynchronous.
