import os
from dotenv import load_dotenv
import mysql.connector
from sshtunnel import SSHTunnelForwarder

load_dotenv(override=True)

print("Starting SSH tunnel...")
tunnel = SSHTunnelForwarder(
    (os.getenv("SSH_HOST"), int(os.getenv("SSH_PORT", "22"))),
    ssh_username=os.getenv("SSH_USER"),
    ssh_password=os.getenv("SSH_PASSWORD"),
    remote_bind_address=(os.getenv("DB_HOST"), int(os.getenv("DB_PORT", "3306")))
)
tunnel.start()
print(f"Tunnel started at local port {tunnel.local_bind_port}")

print("Connecting to database...")
try:
    conn = mysql.connector.connect(
        host="127.0.0.1",
        port=tunnel.local_bind_port,
        database=os.getenv("DB_DATABASE"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        connection_timeout=5
    )
    print("Connected successfully!")
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
finally:
    tunnel.stop()
