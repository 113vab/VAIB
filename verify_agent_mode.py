import urllib.request
import urllib.parse
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def make_request(path, data=None, method="GET"):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    
    if data is not None:
        req_data = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    else:
        req = urllib.request.Request(url, headers=headers, method=method)
        
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            if "application/json" in response.headers.get("Content-Type", ""):
                return json.loads(res_body)
            return res_body
    except Exception as e:
        print(f"Error requesting {method} {path}: {e}")
        return None

if __name__ == "__main__":
    print("--- COMMENCING AUTONOMOUS AGENT MODE VERIFICATION ---")
    time.sleep(1)
    
    # 1. Trigger goal
    print("\n1. Triggering autonomous goal...")
    goal_res = make_request("/api/agent/goals", {"goal": "Check system health and status"}, method="POST")
    if goal_res and "id" in goal_res:
        goal_id = goal_res["id"]
        print(f"SUCCESS: Triggered goal with ID: {goal_id}")
    else:
        print("FAIL: Failed to trigger goal.")
        exit(1)
        
    # 2. Verify goal list
    print("\n2. Verifying Goal List...")
    goals = make_request("/api/agent/goals")
    if goals and len(goals) > 0:
        found = False
        for g in goals:
            if g["id"] == goal_id:
                found = True
                print(f"SUCCESS: Found goal in list (Goal: '{g['goal']}', Status: '{g['status']}')")
                break
        if not found:
             print("FAIL: Goal ID not found in list.")
    else:
        print("FAIL: Goal list is empty or request failed.")
        
    # 3. Wait for background thread execution to perform decomposition and task running
    print("\n3. Waiting for background execution manager...")
    time.sleep(2)
    
    # 4. Fetch goal details & subtasks
    print("\n4. Verifying Goal Details and Subtask queue...")
    detail = make_request(f"/api/agent/goals/{goal_id}")
    if detail and "goal" in detail and "tasks" in detail:
        goal_rec = detail["goal"]
        tasks_rec = detail["tasks"]
        print(f"Goal Status: '{goal_rec['status']}', Result: '{goal_rec['result']}'")
        print(f"Tasks Count: {len(tasks_rec)}")
        for task in tasks_rec:
            print(f"- Step {task['step_number']}: {task['description']} | Tool: {task['tool_name']} | Status: '{task['status']}'")
        if len(tasks_rec) > 0:
            print("SUCCESS: Goal decomposed into tasks and execution loop started.")
        else:
            print("FAIL: Goal was not decomposed into steps.")
    else:
         print("FAIL: Failed to retrieve goal detail.")
         
    # 5. Test cancel/resume goal
    print("\n5. Verifying Goal Cancel and Resume controls...")
    cancel_res = make_request(f"/api/agent/goals/{goal_id}/cancel", method="POST")
    print(f"Cancel request result: {cancel_res}")
    
    resume_res = make_request(f"/api/agent/goals/{goal_id}/resume", method="POST")
    print(f"Resume request result: {resume_res}")
    
    # 6. Test goal deletion
    print("\n6. Verifying Goal Deletion...")
    delete_res = make_request(f"/api/agent/goals/{goal_id}", method="DELETE")
    if delete_res and delete_res.get("status") == "success":
        print("SUCCESS: Goal removed successfully from execution logs.")
    else:
        print("FAIL: Deletion request failed.")
        
    print("\nAutonomous Agent Mode verification complete, Sir.")
