import os
import requests
import json
import time
from dotenv import load_dotenv
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

# Environment Variables
API_KEY = os.environ.get("LOGWATCH_RENDER_API_KEY")
OWNER_ID = os.environ.get("LOGWATCH_RENDER_OWNER_ID")
RESOURCE_ID = os.environ.get("LOGWATCH_RENDER_RESOURCE_ID")

# Use local logs directory if not running in Docker
LOG_DIR = "/logs" if os.path.exists("/logs") else os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")
os.makedirs(LOG_DIR, exist_ok=True)

CURSOR_FILE = os.path.join(LOG_DIR, "render_cursor.txt")
LOG_FILE = os.path.join(LOG_DIR, "render_app.log")
API_URL = "https://api.render.com/v1/logs"

def main():
    if not all([API_KEY, OWNER_ID, RESOURCE_ID]):
        print("[!] Render API credentials missing in environment. Skipping fetch.")
        return

    # Check for cursor
    start_time = None
    if os.path.exists(CURSOR_FILE):
        with open(CURSOR_FILE, "r", encoding="utf-8") as f:
            start_time = f.read().strip()

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json"
    }

    params = {
        "ownerId": OWNER_ID,
        "resource": RESOURCE_ID,
        "limit": 100
    }
    
    if start_time:
        params["startTime"] = start_time
    
    print(f"[*] Fetching Render logs for resource {RESOURCE_ID}...")
    
    all_logs = []
    max_pages = 20  # Prevent infinite loops / rate limits
    page = 0
    
    try:
        while page < max_pages:
            page += 1
            response = requests.get(API_URL, headers=headers, params=params)
            
            if response.status_code == 429:
                print("[!] Rate limit reached. Stopping fetch for now.")
                break
                
            response.raise_for_status()
            data = response.json()
            
            logs = data if isinstance(data, list) else data.get("logs", [])
            
            for log in logs:
                ts = log.get("timestamp", "")
                msg = log.get("message", "")
                level = log.get("level", "INFO") 
                all_logs.append(f"{ts} {level}: {msg.strip()}")
            
            if len(logs) < 100:
                break
                
            if isinstance(data, dict) and "nextStartTime" in data:
                params["startTime"] = data["nextStartTime"]
                time.sleep(1) # Be nice to the API
            else:
                break
                
        if all_logs:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                for line in all_logs:
                    f.write(line + "\n")
            
            print(f"[*] Appended {len(all_logs)} log(s) to {LOG_FILE}.")
            
            last_timestamp = logs[-1].get("timestamp") if logs else start_time
            if last_timestamp:
                with open(CURSOR_FILE, "w", encoding="utf-8") as f:
                    f.write(last_timestamp)
        else:
            print("[*] No new logs found.")
            
    except requests.exceptions.RequestException as e:
        print(f"[!] Error fetching logs from Render API: {e}")

if __name__ == "__main__":
    main()
