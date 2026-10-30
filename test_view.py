
import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv(override=True)

try:
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM vw_unified_matched_enrollment LIMIT 2")
    rows = cursor.fetchall()
    
    print("Database view column keys:")
    if rows:
        print(list(rows[0].keys()))
        print("First row agency_name value:", rows[0].get('agency_name'))
    else:
        print("View returned no rows.")
        
    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error querying database: {e}")
