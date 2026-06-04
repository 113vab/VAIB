import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def send_chat(msg):
    url = f"{BASE_URL}/api/chat"
    data = json.dumps({"message": msg}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as res:
            resp_body = json.loads(res.read().decode("utf-8"))
            print(f"User: '{msg}'\nAI: '{resp_body.get('response')}'\n")
    except Exception as e:
        print(f"Failed for user input '{msg}': {e}")

if __name__ == "__main__":
    print("--- TESTING V.A.I.B. COMMAND ROUTING ---")
    time.sleep(2)  # Wait for server stability
    
    send_chat("open github.com")
    send_chat("open youtube.com")
    send_chat("search google for python")
