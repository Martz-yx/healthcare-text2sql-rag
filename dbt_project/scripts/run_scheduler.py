import os
import sys
import time
import subprocess
from datetime import datetime, timedelta

def run_dbt(retries=3, delay=60):
    project_dir = "/usr/app/dbt_project"
    for attempt in range(1, retries + 1):
        print(f"[{datetime.now()}] --- STARTING DBT RUN (Attempt {attempt}/{retries}) ---")
        sys.stdout.flush()
        res = subprocess.run(["dbt", "run", "--profiles-dir", project_dir], cwd=project_dir)
        if res.returncode == 0:
            print(f"[{datetime.now()}] dbt run finished successfully.")
            sys.stdout.flush()
            print(f"[{datetime.now()}] Compiling dbt docs catalog...")
            res_compile = subprocess.run(["dbt", "docs", "generate", "--profiles-dir", project_dir], cwd=project_dir)
            print(f"[{datetime.now()}] dbt compile finished with exit code: {res_compile.returncode}")
            sys.stdout.flush()
            return True
        else:
            print(f"[{datetime.now()}] dbt run failed with exit code: {res.returncode}. Retrying in {delay}s...")
            sys.stdout.flush()
            time.sleep(delay)
    print(f"[{datetime.now()}] ERROR: dbt run failed after {retries} attempts!")
    sys.stdout.flush()
    return False

def start_docs_server():
    import threading
    import http.server
    import socketserver
    
    def serve():
        target_dir = "/usr/app/dbt_project/target"
        os.makedirs(target_dir, exist_ok=True)
        os.chdir(target_dir)
        
        if not os.path.exists("index.html"):
            import urllib.request
            try:
                urllib.request.urlretrieve("https://raw.githubusercontent.com/dbt-labs/dbt-docs/main/index.html", "index.html")
            except Exception:
                pass
                
        class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
            def end_headers(self):
                self.send_header('Access-Control-Allow-Origin', '*')
                super().end_headers()
                
        port = 8080
        with socketserver.TCPServer(("", port), CORSRequestHandler) as httpd:
            print(f"[{datetime.now()}] Serving DBT Docs on port {port}")
            httpd.serve_forever()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()

if __name__ == "__main__":
    print(f"[{datetime.now()}] DBT Scheduler started.")
    sys.stdout.flush()
    
    # Start the docs HTTP server in background
    start_docs_server()
    
    # Run once on startup to sync the database
    run_dbt()
    
    while True:
        # Calculate time until 01:00 AM (local container timezone)
        now = datetime.now()
        target = now.replace(hour=1, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        
        sleep_seconds = (target - now).total_seconds()
        print(f"[{datetime.now()}] Next scheduled run at {target}. Sleeping for {sleep_seconds:.1f} seconds...")
        sys.stdout.flush()
        
        time.sleep(sleep_seconds)
        run_dbt()

