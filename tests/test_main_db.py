import os
from dotenv import load_dotenv
import mysql.connector
from sshtunnel import SSHTunnelForwarder
from app.db import database

load_dotenv(override=True)

database.DB_CONFIG.update({
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "database": os.getenv("DB_DATABASE"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
})

tunnel_kwargs = {
    "ssh_address_or_host": (os.getenv("SSH_HOST"), int(os.getenv("SSH_PORT", "22"))),
    "ssh_username": os.getenv("SSH_USER"),
    "ssh_password": os.getenv("SSH_PASSWORD"),
    "remote_bind_address": (database.DB_CONFIG["host"], database.DB_CONFIG["port"])
}

database.ssh_tunnel = SSHTunnelForwarder(**tunnel_kwargs)
database.ssh_tunnel.start()

print(f"Tunnel local port: {database.ssh_tunnel.local_bind_port}")

print("Calling get_db_config()...")
config = database.get_db_config()
print(f"Config: {config}")

print("Connecting...")
try:
    conn = mysql.connector.connect(**config)
    print("Connected successfully!")
    cursor = conn.cursor(dictionary=True)
    print("Checking processlist...")
    cursor.execute("SHOW PROCESSLIST")
    processes = cursor.fetchall()
    for p in processes:
        print(p)
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
finally:
    database.ssh_tunnel.stop()
