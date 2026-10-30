from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
import mysql.connector
from mysql.connector import Error

from app.db.database import get_db_connection
from app.schemas.schemas import UserCreate
from app.core.security import (
    authenticate_user, 
    create_access_token,
    create_refresh_token,
    get_password_hash,
    REFRESH_SECRET_KEY,
    ALGORITHM
)
import jwt

router = APIRouter(tags=["Authentication"])

@router.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db = Depends(get_db_connection)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user["username"]}
    )
    refresh_token = create_refresh_token(
        data={"sub": user["username"]}
    )
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

from pydantic import BaseModel
class RefreshTokenRequest(BaseModel):
    refresh_token: str

@router.post("/refresh")
async def refresh_access_token(request: RefreshTokenRequest, db = Depends(get_db_connection)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(request.refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise credentials_exception
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise credentials_exception

    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM api_users WHERE username = %s", (username,))
        user = cursor.fetchone()
    finally:
        cursor.close()

    if user is None or user.get("disabled"):
        raise credentials_exception

    access_token = create_access_token(
        data={"sub": user["username"]}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/signup", status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, db = Depends(get_db_connection)):
    cursor = db.cursor(dictionary=True)
    try:
        # Check if username already exists
        cursor.execute("SELECT id FROM api_users WHERE username = %s", (user.username,))
        existing_user = cursor.fetchone()
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already registered")
            
        hashed_password = get_password_hash(user.password)
        cursor.execute(
            "INSERT INTO api_users (username, hashed_password) VALUES (%s, %s)",
            (user.username, hashed_password)
        )
        db.commit()
    except Error as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        
    return {"message": "User created successfully. You can now log in."}
