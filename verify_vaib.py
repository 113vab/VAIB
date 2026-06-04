import urllib.request
import urllib.parse
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def make_request(path, data=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    
    if data is not None:
        req_data = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method="POST")
    else:
        req = urllib.request.Request(url, method="GET")
        
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            if "application/json" in response.headers.get("Content-Type", ""):
                return json.loads(res_body)
            return res_body
    except Exception as e:
        print(f"Error requesting {path}: {e}")
        return None

if __name__ == "__main__":
    print("--- COMMENCING V.A.I.B. LOCAL VERIFICATION ---")
    time.sleep(2)  # Wait for server stability
    
    # 1. Verify dashboard loads
    print("\n1. Verifying Dashboard loads...")
    html = make_request("/")
    if html and "V.A.I.B." in html:
        print("SUCCESS: Dashboard index loaded and contains V.A.I.B. tags.")
    else:
        print("FAIL: Dashboard failed to load.")
        
    # 2. Verify Gemini chat works (in simulation mode fallback)
    print("\n2. Verifying Chat Endpoint...")
    chat_res = make_request("/api/chat", {"message": "Hello VAIB"})
    if chat_res and "response" in chat_res:
        print(f"SUCCESS: Chat returned: '{chat_res['response']}'")
    else:
        print("FAIL: Chat endpoint did not return response.")
        
    # 3. Verify Voice Output works (edge-tts generates MP3)
    print("\n3. Verifying Voice Output (TTS) Endpoint...")
    tts_res = make_request("/api/tts", {"text": "Welcome back, Sir."})
    if tts_res and "audio_url" in tts_res:
        print(f"SUCCESS: Voice output generated cache URL: {tts_res['audio_url']}")
    else:
        print("FAIL: Voice output failed to generate file URL.")
        
    # 4. Verify Memory persists (Save Fact)
    print("\n4. Verifying Memory Storage...")
    save_res = make_request("/api/chat", {"message": "remember my favorite language is Python"})
    print(f"Chat response (save preference): '{save_res.get('response') if save_res else 'None'}'")
    
    # 5. Verify Memory persists (Recall Fact)
    print("\n5. Verifying Memory Recall...")
    status_res = make_request("/api/chat", {"message": "what is my favorite language?"})
    print(f"Chat response (recall preference): '{status_res.get('response') if status_res else 'None'}'")
    
    # 6. Verify Reminders & Alarm Scheduler
    print("\n6. Verifying Reminders/Alarms...")
    rem_res = make_request("/api/chat", {"message": "remind me to call the chief in 1 second"})
    print(f"Chat response (set reminder): '{rem_res.get('response') if rem_res else 'None'}'")
    time.sleep(2)
    poll_res = make_request("/api/notifications/poll")
    if poll_res and "notifications" in poll_res:
        notifs = poll_res["notifications"]
        print(f"SUCCESS: Notification poll returned {len(notifs)} items: {notifs}")
    else:
        print("FAIL: Failed to poll triggered reminders.")

    # 7. Verify Calendar event
    print("\n7. Verifying Calendar Events...")
    cal_res = make_request("/api/chat", {"message": "add event Team Sync on 2026-06-05 at 10:00"})
    print(f"Chat response (add calendar event): '{cal_res.get('response') if cal_res else 'None'}'")
    list_cal = make_request("/api/chat", {"message": "show my calendar"})
    print(f"Chat response (list calendar): '{list_cal.get('response') if list_cal else 'None'}'")

    # 8. Verify dynamic plugins loading
    print("\n8. Verifying Dynamic Plugins...")
    from pathlib import Path
    plugins_dir = Path("plugins")
    if plugins_dir.exists() and (plugins_dir / "example_plugin.py").exists():
        print("SUCCESS: Dynamic plugins directory exists and example_plugin.py is generated.")
    else:
        print("FAIL: Dynamic plugins directory or example_plugin.py not found.")
        
    print("\nVerification process complete, Sir.")

