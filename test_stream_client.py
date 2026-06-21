import httpx
import time
import asyncio
import subprocess
import sys
import traceback

async def main():
    print("Starting server process...")
    # Remove pipes to prevent buffer clog hang
    server_process = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd="C:/Users/visha/friday"
    )
    # Wait for server to load
    await asyncio.sleep(9.0)
    
    print("Initiating streaming request...")
    url = "http://127.0.0.1:8000/api/chat/stream"
    payload = {"message": "Write a short reply with three sentences. Each sentence should end with a period."}
    
    start_time = time.time()
    first_token_time = None
    chunks_received = 0
    
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, json=payload, timeout=20.0) as response:
                assert response.status_code == 200
                print(f"Connection established in {time.time() - start_time:.3f}s")
                
                async for chunk in response.aiter_text():
                    if chunks_received == 0:
                        first_token_time = time.time() - start_time
                        print(f"First chunk received at: {first_token_time:.3f}s")
                    chunks_received += 1
                    elapsed = time.time() - start_time
                    print(f"Chunk {chunks_received} ({len(chunk)} chars): '{chunk}' at {elapsed:.3f}s")
                    
    except Exception as e:
        print(f"Request failed: {e}")
        traceback.print_exc()
    finally:
        print("Terminating server...")
        server_process.terminate()
        server_process.wait()
        print("Server terminated.")

if __name__ == "__main__":
    asyncio.run(main())
