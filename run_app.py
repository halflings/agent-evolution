import sys
import subprocess
import threading
import time
import os
import socket

def find_next_free_port(start_port):
    port = start_port
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            port += 1

def run_backend(port):
    print(f"[Backend] Starting FastAPI server on http://localhost:{port}...")
    # Run uvicorn using uv run python -m uvicorn
    cmd = ["uv", "run", "python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)]
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[Backend] Error: {e}")

def run_frontend(port, backend_port):
    print(f"[Frontend] Starting Next.js dev server on http://localhost:{port}...")
    # Change Cwd to frontend and run npm run dev
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
    cmd = ["npm", "run", "dev", "--", "-p", str(port)]
    
    # Pass NEXT_PUBLIC_API_URL to the frontend process
    env = os.environ.copy()
    env["NEXT_PUBLIC_API_URL"] = f"http://localhost:{backend_port}"
    
    try:
        subprocess.run(cmd, cwd=frontend_path, check=True, env=env)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[Frontend] Error: {e}")

def main():
    backend_port = find_next_free_port(8080)
    frontend_port = find_next_free_port(3000)

    print("=========================================")
    print("     Starting Agent Evolution Web Hub    ")
    print("=========================================")
    
    # Start backend thread
    backend_thread = threading.Thread(target=run_backend, args=(backend_port,), daemon=True)
    backend_thread.start()
    
    # Give backend a moment to bind to the port
    time.sleep(2)
    
    # Start frontend thread
    frontend_thread = threading.Thread(target=run_frontend, args=(frontend_port, backend_port), daemon=True)
    frontend_thread.start()
    
    print("\n🚀 Both servers starting up concurrently!")
    print(f"👉 Frontend: http://localhost:{frontend_port}")
    print(f"👉 Backend API: http://localhost:{backend_port}/docs")
    print("Press Ctrl+C to terminate both servers...\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping all services...")
        sys.exit(0)

if __name__ == "__main__":
    main()
