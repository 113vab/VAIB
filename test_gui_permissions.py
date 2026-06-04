import asyncio
from playwright.async_api import async_playwright
import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def trigger_close_notepad():
    url = f"{BASE_URL}/api/chat"
    data = json.dumps({"message": "close notepad"}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as res:
            print("Trigger response:", res.read().decode("utf-8"))
    except Exception as e:
        print("Failed to trigger close notepad:", e)

async def check_gui():
    trigger_close_notepad()
    time.sleep(1) # wait for polling/db update

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Listen to console events
        page.on("console", lambda msg: print(f"BROWSER CONSOLE: {msg.text}"))
        
        await page.goto(BASE_URL)
        
        # Wait for the panel-permissions to become visible
        try:
            await page.wait_for_selector("#panel-permissions", state="visible", timeout=5000)
            print("Permissions panel is visible!")
        except Exception:
            print("Permissions panel NOT visible after 5s.")
            
        html_before = await page.eval_on_selector("#panel-permissions", "el => el.outerHTML")
        print("\n--- HTML Before Approve ---")
        print(html_before)
        
        # Click APPROVE button
        print("\nClicking APPROVE...")
        await page.click(".approve-btn")
        
        # Wait a bit for execution
        await page.wait_for_timeout(2000)
        
        # Check console stream
        console_lines = await page.locator("#console-stream .console-line").all_inner_texts()
        print("\n--- Console Stream Lines After Approve ---")
        for line in console_lines[-5:]:
            print(line)
            
        # Check chat messages
        chat_msgs = await page.locator("#chat-messages .chat-bubble").all_inner_texts()
        print("\n--- Chat Messages ---")
        for msg in chat_msgs[-3:]:
            print(msg.replace("\n", " | "))

        await browser.close()

if __name__ == "__main__":
    asyncio.run(check_gui())
