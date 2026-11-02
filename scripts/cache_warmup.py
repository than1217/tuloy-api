import os
import time
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_URL = os.getenv("TULOY_API_BASE_URL", "http://127.0.0.1:8000")
USERNAME = os.getenv("TULOY_API_USERNAME")
PASSWORD = os.getenv("TULOY_API_PASSWORD")

def login():
    print(f"Logging in as {USERNAME}...")
    response = requests.post(
        f"{BASE_URL}/token",
        data={"username": USERNAME, "password": PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    response.raise_for_status()
    return response.json()["access_token"]

def warmup_cache(token):
    headers = {"Authorization": f"Bearer {token}"}
    offset = 0
    limit = 5000

    print(f"Warming up cache for /GetEligibleBene (batch size: {limit})...")
    
    start_time = time.time()
    pages_cached = 0
    total_records = 0

    while True:
        try:
            page_start = time.time()
            response = requests.get(
                f"{BASE_URL}/GetEligibleBene", 
                headers=headers, 
                params={"limit": limit, "offset": offset}
            )
            response.raise_for_status()
            data = response.json()
            
            page_time = time.time() - page_start
            records_in_page = len(data.get("items", []))
            total_records += records_in_page
            pages_cached += 1
            
            print(f"Cached offset {offset} ({records_in_page} records) in {page_time:.2f}s")
            
            if not data.get("has_more"):
                break
            
            offset = data.get("next_offset")
            
            # Small delay to ensure we don't completely lock up the database 
            # if it's currently serving other traffic during warmup
            time.sleep(0.1) 
            
        except Exception as e:
            print(f"Error during cache warmup at offset {offset}: {e}")
            break

    total_time = time.time() - start_time
    print("-" * 40)
    print(f"Cache warmup complete in {total_time:.2f} seconds!")
    print(f"Total pages cached: {pages_cached}")
    print(f"Total records processed: {total_records}")

if __name__ == "__main__":
    if not USERNAME or not PASSWORD:
        print("Error: TULOY_API_USERNAME and TULOY_API_PASSWORD must be set in .env")
        exit(1)
        
    try:
        token = login()
        warmup_cache(token)
    except Exception as e:
        print(f"Fatal error: {e}")
