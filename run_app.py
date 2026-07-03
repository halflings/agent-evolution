import sys
import subprocess
import threading
import time
import os

def run_backend():
    print("[Backend] Starting FastAPI server on http://localhost:8080...")
    # Run uvicorn using uv run
    cmd = ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[Backend] Error: {e}")

def run_frontend():
    print("[Frontend] Starting Next.js dev server on http://localhost:3000...")
    # Change Cwd to frontend and run npm run dev
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
    cmd = ["npm", "run", "dev"]
    try:
        subprocess.run(cmd, cwd=frontend_path, check=True)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[Frontend] Error: {e}")

def main():
    print("=========================================")
    print("     Starting Agent Evolution Web Hub    ")
    print("=========================================")
    
    # Start backend thread
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    
    # Give backend a moment to bind to the port
    time.sleep(2)
    
    # Start frontend thread
    frontend_thread = threading.Thread(target=run_frontend, daemon=True)
    frontend_thread.start()
    
    print("\n🚀 Both servers starting up concurrently!")
    print("👉 Frontend: http://localhost:3000")
    print("👉 Backend API: http://localhost:8080/docs")
    print("Press Ctrl+C to terminate both servers...\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping all services...")
        sys.exit(0)

if __name__ == "__main__":
    main()
