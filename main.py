from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import hashlib
import re
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="User Match API")

# Database connection configuration
DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'database': os.getenv("DB_DATABASE"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD")
}

class UserInput(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: str  # e.g., 'YYYY-MM-DD'

def get_db_connection():
    """Dependency to get a database connection per request"""
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        yield conn
    except Error as e:
        print(f"\n[ERROR] Database connection error: {e}\n")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
    finally:
        if conn and conn.is_connected():
            conn.close()

def generate_md5_hash(first_name: str, last_name: str, dob: str) -> str:
    """Generate MD5 hash from the inputs to match the database match_keys format."""
    first_clean = re.sub(r'\s+', ' ', first_name).strip().upper()
    last_clean = re.sub(r'\s+', ' ', last_name).strip().upper()
    raw_string = f"{first_clean}/{last_clean}/{dob}"
    return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

@app.post("/VerifyMemberBene")
def match_user(user: UserInput, db = Depends(get_db_connection)):
    cursor = db.cursor(dictionary=True)
    
    # 1. Generate the hash (for the response)
    user_hash = generate_md5_hash(user.first_name, user.last_name, user.date_of_birth)
    
    try:
        # 2. Query the source table
        select_query = r"""
            SELECT * FROM vw_verify_member_bene 
            WHERE match_keys = MD5(CONCAT_WS('/', 
                UPPER(TRIM(REGEXP_REPLACE(%s, '\\s+', ' '))),
                UPPER(TRIM(REGEXP_REPLACE(%s, '\\s+', ' '))), 
                %s
            ))
        """
        cursor.execute(select_query, (user.first_name, user.last_name, user.date_of_birth))
        results = cursor.fetchall()
        
        row_count = len(results)
        
        # 3. Check the conditions
        if row_count == 0:
            return {"status": "Not Found", "md5_hash": user_hash}
            
        elif row_count >= 2:
            return {"status": "Multiple Match Found", "md5_hash": user_hash}
            
        elif row_count == 1:
            return {"status": "Matched", "md5_hash": user_hash}
            
    except Error as e:
        print(f"\n[ERROR] Database error during verification: {e}\n")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
