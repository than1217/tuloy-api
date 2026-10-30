import os
import csv
import json
import mysql.connector
from dotenv import load_dotenv

# Load env
load_dotenv(override=True)

# Set up SSH Tunnel if needed
ssh_tunnel = None
ssh_host = os.getenv("SSH_HOST")

if ssh_host:
    try:
        from sshtunnel import SSHTunnelForwarder
        ssh_port = int(os.getenv("SSH_PORT", "22"))
        ssh_user = os.getenv("SSH_USER")
        ssh_password = os.getenv("SSH_PASSWORD")
        ssh_pkey = os.getenv("SSH_PKEY")

        tunnel_kwargs = {
            "ssh_address_or_host": (ssh_host, ssh_port),
            "ssh_username": ssh_user,
            "remote_bind_address": (os.getenv("DB_HOST"), int(os.getenv("DB_PORT", 3306)))
        }
        if ssh_pkey:
            tunnel_kwargs["ssh_pkey"] = ssh_pkey
        if ssh_password:
            tunnel_kwargs["ssh_password"] = ssh_password

        ssh_tunnel = SSHTunnelForwarder(**tunnel_kwargs)
        ssh_tunnel.start()
        print(f"SSH tunnel established. Local bind port: {ssh_tunnel.local_bind_port}")
        
        db_config = {
            "host": "127.0.0.1",
            "port": ssh_tunnel.local_bind_port,
            "database": os.getenv("DB_DATABASE"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
        }
    except Exception as e:
        print(f"Failed to establish SSH tunnel: {e}")
        exit(1)
else:
    db_config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 3306)),
        "database": os.getenv("DB_DATABASE", "tuloy"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
    }

print("Connecting to DB...")
try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    print("Connected.")
except Exception as e:
    print(f"DB connection failed: {e}")
    if ssh_tunnel:
        ssh_tunnel.stop()
    exit(1)

CSV_PATH = r"C:\Users\jfigueroa\Desktop\DSWD\Tuloy\tuloy-api\others\TESDA Matching 136.csv"

def clean_val(v):
    if not v or str(v).strip() == "":
        return None
    return str(v).strip()

inserted_txn = 0
inserted_data = 0

try:
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tuloy_id = clean_val(row.get('TULOY ID'))
            verify_status = clean_val(row.get('VERIFY STATUS'))
            
            if verify_status == "Matched":
                status_str = "FOUND"
            elif verify_status and "multiple" in verify_status.lower():
                status_str = "MULTIPLE MATCH FOUND"
            else:
                status_str = "NOT FOUND"
                
            # Insert into txn table
            cursor.execute(
                "INSERT INTO matching_transaction_TESDA_tbl (tuloy_id, status) VALUES (%s, %s)",
                (tuloy_id, status_str)
            )
            match_id = cursor.lastrowid
            inserted_txn += 1
            
            if status_str == "FOUND":
                enrollment_id = 0
                member_id = clean_val(row.get('MEMBER ID'))
                uli_id = clean_val(row.get('ULI'))
                mm_first_name = clean_val(row.get('FIRST NAME'))
                mm_middle_name = clean_val(row.get('MIDDLE NAME'))
                mm_last_name = clean_val(row.get('LAST NAME'))
                
                diploma_json = "{}"
                
                short_course_dict = {
                    "program_name": clean_val(row.get('QUALIFICATION')),
                    "start_date": clean_val(row.get('START DATE')),
                    "end_date": clean_val(row.get('END DATE')),
                    "training_status": clean_val(row.get('TRAINING STATUS')),
                }
                short_course_json = json.dumps({k: v for k, v in short_course_dict.items() if v is not None})
                
                cursor.execute("""
                    INSERT INTO enroll_matched_TESDA_tbl (
                        match_id, enrollment_id, tuloy_id, member_id, uli_id,
                        mm_first_name, mm_middle_name, mm_last_name,
                        diploma, short_course
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s
                    )
                """, (
                    match_id, enrollment_id, tuloy_id, member_id, uli_id,
                    mm_first_name, mm_middle_name, mm_last_name,
                    diploma_json, short_course_json
                ))
                inserted_data += 1
                
    conn.commit()
    print(f"Successfully inserted {inserted_txn} transactions and {inserted_data} matched records.")
except Exception as e:
    conn.rollback()
    print(f"Error during insert: {e}")
finally:
    cursor.close()
    conn.close()
    if ssh_tunnel:
        ssh_tunnel.stop()
