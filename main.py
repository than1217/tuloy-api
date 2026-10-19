from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
import hashlib
import re
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
import bcrypt
from contextlib import asynccontextmanager
try:
    from sshtunnel import SSHTunnelForwarder
except ImportError:
    SSHTunnelForwarder = None

load_dotenv()

# Database connection configuration
DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'port': int(os.getenv("DB_PORT", 3306)),
    'database': os.getenv("DB_DATABASE"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD")
}

ssh_tunnel = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global ssh_tunnel

    ssh_host = os.getenv("SSH_HOST")
    try:
        try:
            if ssh_host:
                if SSHTunnelForwarder is None:
                    raise RuntimeError(
                        "SSH_HOST is set but sshtunnel is not installed. Install requirements."
                    )

                ssh_port = int(os.getenv("SSH_PORT", "22"))
                ssh_user = os.getenv("SSH_USER")
                ssh_password = os.getenv("SSH_PASSWORD")
                ssh_pkey = os.getenv("SSH_PKEY")

                if not ssh_user:
                    raise RuntimeError("SSH_USER is required when SSH_HOST is set.")
                if not ssh_password and not ssh_pkey:
                    raise RuntimeError(
                        "Set SSH_PASSWORD or SSH_PKEY when SSH_HOST is set."
                    )

                tunnel_kwargs = {
                    "ssh_address_or_host": (ssh_host, ssh_port),
                    "ssh_username": ssh_user,
                    "remote_bind_address": (DB_CONFIG["host"], DB_CONFIG["port"])
                }
                if ssh_pkey:
                    tunnel_kwargs["ssh_pkey"] = ssh_pkey
                if ssh_password:
                    tunnel_kwargs["ssh_password"] = ssh_password

                ssh_tunnel = SSHTunnelForwarder(**tunnel_kwargs)
                ssh_tunnel.start()
                print(f"SSH tunnel established. Local bind port: {ssh_tunnel.local_bind_port}")
        except Exception as e:
            raise RuntimeError(
                f"Failed to establish SSH tunnel to {ssh_host}: {e}"
            ) from e

        conn = None
        cursor = None
        try:
            conn = mysql.connector.connect(**get_db_config())
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    hashed_password VARCHAR(255) NOT NULL,
                    disabled BOOLEAN DEFAULT FALSE
                )
            """)
            conn.commit()
            print("Initialized api_users table successfully.")
        except Error as e:
            raise RuntimeError(f"Error initializing database: {e}") from e
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        yield
    finally:
        if ssh_tunnel:
            ssh_tunnel.stop()
            ssh_tunnel = None
            print("SSH tunnel closed.")


def get_db_config():
    config = DB_CONFIG.copy()
    if ssh_tunnel:
        config["host"] = "127.0.0.1"
        config["port"] = ssh_tunnel.local_bind_port
    return config

app = FastAPI(title="Tuloy API", lifespan=lifespan)

# --- Authentication Configuration ---
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-for-jwt")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_db_connection():
    """Dependency to get a database connection per request"""
    conn = None
    try:
        conn = mysql.connector.connect(**get_db_config())
        yield conn
    except Error as e:
        print(f"\n[ERROR] Database connection error: {e}\n")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
    finally:
        if conn and conn.is_connected():
            conn.close()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))

def get_password_hash(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def authenticate_user(db, username: str, password: str):
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM api_users WHERE username = %s", (username,))
        user = cursor.fetchone()
    finally:
        cursor.close()
        
    if not user:
        return False
    if not verify_password(password, user["hashed_password"]):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db = Depends(get_db_connection)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception
        
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM api_users WHERE username = %s", (username,))
        user = cursor.fetchone()
    finally:
        cursor.close()
        
    if user is None:
        raise credentials_exception
    if user.get("disabled"):
        raise HTTPException(status_code=400, detail="Inactive user")
    return user

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db = Depends(get_db_connection)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# -----------------------------------

class UserCreate(BaseModel):
    username: str
    password: str

@app.post("/signup", status_code=status.HTTP_201_CREATED)
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

class UserInput(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    date_of_birth: str  # e.g., 'YYYY-MM-DD'
    sex: Optional[str] = None
    member_id: Optional[str] = None
    household_id: Optional[str] = None
    lrn: Optional[str] = None
    pcn: Optional[str] = None
    geocode: Optional[str] = None

def generate_md5_hash(first_name: str, last_name: str, dob: str) -> str:
    """Generate MD5 hash from the inputs to match the database match_keys format."""
    first_clean = re.sub(r'\s+', ' ', first_name).strip().upper()
    last_clean = re.sub(r'\s+', ' ', last_name).strip().upper()
    raw_string = f"{first_clean}/{last_clean}/{dob}"
    return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

@app.post("/VerifyMemberBene")
def match_user(user: UserInput, current_user: dict = Depends(get_current_user), db = Depends(get_db_connection)):
    cursor = db.cursor(dictionary=True)
    
    # 1. Generate the hash (for the response)
    user_hash = generate_md5_hash(user.first_name, user.last_name, user.date_of_birth)
    optional_filters = {
        "middle_name": user.middle_name,
        "sex": user.sex,
        "member_id": user.member_id,
        "household_id": user.household_id,
        "lrn": user.lrn,
        "pcn": user.pcn,
        "geocode": user.geocode,
    }
    optional_filter_columns = {
        "middle_name": "middle_name",
        "sex": "sex_id",
        "member_id": "member_id",
        "household_id": "listahanan_id",
        "lrn": "lrn",
        "pcn": "philsys",
        "geocode": "bgy_psgc_code",
    }
    
    try:
        # 2. Query the source table
        select_query = r"""
            SELECT * FROM vw_verify_member_bene 
            WHERE match_keys = UNHEX(MD5(CONCAT_WS('/', 
                UPPER(TRIM(REGEXP_REPLACE(%s, '\\s+', ' '))),
                UPPER(TRIM(REGEXP_REPLACE(%s, '\\s+', ' '))), 
                %s
            )))
        """
        query_params = [user.first_name, user.last_name, user.date_of_birth]
        for field, value in optional_filters.items():
            if value is not None:
                select_query += f" AND {optional_filter_columns[field]} = %s"
                query_params.append(value)

        cursor.execute(select_query, tuple(query_params))
        results = cursor.fetchall()
        
        row_count = len(results)
        
        # 3. Check the conditions
        if row_count == 0:
            return {"status": "Not Found", "md5_hash": user_hash, "member_id": None}
            
        elif row_count >= 2:
            return {"status": "Multiple Match Found", "md5_hash": user_hash, "member_id": None}
            
        elif row_count == 1:
            return {
                "status": "Matched",
                "md5_hash": user_hash,
                "member_id": results[0].get("member_id"),
            }
            
    except Error as e:
        print(f"\n[ERROR] Database error during verification: {e}\n")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
