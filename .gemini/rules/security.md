# API Security Rules

## Authentication
- The app uses JWT (`PyJWT`) with `bcrypt` for password hashing, implemented in `app.core.security`.
- Protect routes by injecting the dependency: `current_user = Depends(get_current_user)`.
- The `get_current_user` dependency automatically handles 401 errors for invalid or expired tokens.

## Passwords
- Passwords MUST be hashed using bcrypt before insertion.
- Due to bcrypt limitations, passwords must be truncated to 72 bytes before hashing: `password.encode("utf-8")[:72]`.
