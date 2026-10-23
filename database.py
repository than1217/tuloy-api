import os
import mysql.connector
from mysql.connector import Error
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv(override=True)

DB_CONFIG = {
    'host': os.getenv("DB_HOST"),
    'port': int(os.getenv("DB_PORT", 3306)),
    'database': os.getenv("DB_DATABASE"),
    'user': os.getenv("DB_USER"),
    'password': os.getenv("DB_PASSWORD")
}

ssh_tunnel = None

def get_db_config():
    config = DB_CONFIG.copy()
    if ssh_tunnel:
        if not ssh_tunnel.is_active:
            ssh_tunnel.start()
        config["host"] = "127.0.0.1"
        config["port"] = ssh_tunnel.local_bind_port
    return config

def get_db_connection():
    """Dependency to get a database connection per request"""
    conn = None
    try:
        conn = mysql.connector.connect(**get_db_config())
        yield conn
    except Error as e:
        print(f"\\n[ERROR] Database connection error: {e}\\n")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")
    finally:
        if conn and conn.is_connected():
            conn.close()
