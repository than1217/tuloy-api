import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv(override=True)
config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'database': os.getenv('DB_DATABASE', 'tuloy'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '')
}
try:
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()
    print("TESDA tables:")
    cursor.execute("SHOW TABLES LIKE '%TESDA%'")
    for row in cursor.fetchall():
        print(row)
    
    print("CHED tables:")
    cursor.execute("SHOW TABLES LIKE '%ched%'")
    for row in cursor.fetchall():
        print(row)
except Exception as e:
    print(e)
