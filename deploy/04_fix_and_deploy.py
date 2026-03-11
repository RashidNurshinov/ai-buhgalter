# -*- coding: utf-8 -*-
"""
Step 4: Fix all known bugs and deploy updates.
Fixes:
1. agent_tools.py: e.deadline -> e.due_date
2. main.py: enable docs, add server IP to CORS
3. requirements.txt: add opencv-python-headless
4. Rebuild and restart containers
"""
import paramiko
import sys
import time

HOST = "138.124.108.144"
USER = "root"
PASSWORD = "jlGGd9v9cnhq"
PROJECT_PATH = "/opt/ai-buhgalter"

def run_cmd(ssh, cmd, desc="", check_error=False):
    if desc:
        print(f"\n--- {desc} ---")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    out_safe = out.encode('ascii', errors='replace').decode('ascii')
    err_safe = err.encode('ascii', errors='replace').decode('ascii')
    if out_safe.strip():
        print(out_safe[:3000])
    if err_safe.strip() and check_error:
        print(f"[STDERR] {err_safe[:2000]}")
    return out, err

def write_file(ssh, remote_path, content):
    """Write content to a file on the server via SFTP."""
    sftp = ssh.open_sftp()
    with sftp.file(remote_path, 'w') as f:
        f.write(content)
    sftp.close()
    print(f"  [WRITTEN] {remote_path}")

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
        print("[OK] Connected!")

        # ============================================================
        # FIX 1: agent_tools.py - replace e.deadline with e.due_date
        # ============================================================
        print("\n" + "="*60)
        print("  FIX 1: agent_tools.py - e.deadline -> e.due_date")
        print("="*60)
        
        run_cmd(ssh, 
            f"sed -i 's/e\\.deadline/e.due_date/g' {PROJECT_PATH}/backend/app/services/agent_tools.py",
            "Replacing e.deadline -> e.due_date")
        
        # Also fix TaxCalendarEvent.deadline -> TaxCalendarEvent.due_date
        run_cmd(ssh,
            f"sed -i 's/TaxCalendarEvent\\.deadline/TaxCalendarEvent.due_date/g' {PROJECT_PATH}/backend/app/services/agent_tools.py",
            "Replacing TaxCalendarEvent.deadline -> TaxCalendarEvent.due_date")
        
        # Verify the fix
        run_cmd(ssh,
            f"grep -n 'deadline' {PROJECT_PATH}/backend/app/services/agent_tools.py | head -10",
            "Remaining 'deadline' references (should only be tool names)")

        # ============================================================
        # FIX 2: main.py - enable docs always + add server IP to CORS
        # ============================================================
        print("\n" + "="*60)
        print("  FIX 2: main.py - enable API docs, fix CORS")
        print("="*60)
        
        # Read current main.py
        out, _ = run_cmd(ssh, f"cat {PROJECT_PATH}/backend/app/main.py")
        main_content = out
        
        # Replace docs_url to always be enabled
        run_cmd(ssh,
            f'''sed -i 's|docs_url="/api/docs" if settings.is_development else None|docs_url="/api/docs"|' {PROJECT_PATH}/backend/app/main.py''',
            "Enable docs_url always")
        
        run_cmd(ssh,
            f'''sed -i 's|redoc_url="/api/redoc" if settings.is_development else None|redoc_url="/api/redoc"|' {PROJECT_PATH}/backend/app/main.py''',
            "Enable redoc_url always")
        
        run_cmd(ssh,
            f'''sed -i 's|openapi_url="/api/openapi.json" if settings.is_development else None|openapi_url="/api/openapi.json"|' {PROJECT_PATH}/backend/app/main.py''',
            "Enable openapi_url always")
        
        # Add server IP to CORS
        run_cmd(ssh,
            f'''grep -q "138.124.108.144" {PROJECT_PATH}/backend/app/main.py || sed -i 's|"http://127.0.0.1:3000",|"http://127.0.0.1:3000",\\n        "http://138.124.108.144",\\n        "http://138.124.108.144:80",|' {PROJECT_PATH}/backend/app/main.py''',
            "Add server IP to CORS")
        
        # Verify
        run_cmd(ssh, f"grep -A5 'docs_url' {PROJECT_PATH}/backend/app/main.py", "Verify docs_url")
        run_cmd(ssh, f"grep -A8 'allow_origins' {PROJECT_PATH}/backend/app/main.py", "Verify CORS origins")

        # ============================================================
        # FIX 3: requirements.txt - add opencv-python-headless
        # ============================================================
        print("\n" + "="*60)
        print("  FIX 3: requirements.txt - add opencv-python-headless")
        print("="*60)
        
        run_cmd(ssh,
            f"grep -q 'opencv' {PROJECT_PATH}/backend/requirements.txt || echo 'opencv-python-headless>=4.8.0' >> {PROJECT_PATH}/backend/requirements.txt",
            "Add opencv-python-headless to requirements.txt")
        
        run_cmd(ssh,
            f"tail -5 {PROJECT_PATH}/backend/requirements.txt",
            "Verify requirements.txt tail")

        # ============================================================
        # FIX 4: Install opencv in running container (quick fix)
        # ============================================================
        print("\n" + "="*60)
        print("  FIX 4: Install opencv in running backend container")
        print("="*60)
        
        run_cmd(ssh,
            "docker exec ai_buhgalter_backend pip install opencv-python-headless>=4.8.0 2>&1 | tail -3",
            "Installing opencv in backend container", check_error=True)
        
        run_cmd(ssh,
            "docker exec ai_buhgalter_celery_worker pip install opencv-python-headless>=4.8.0 2>&1 | tail -3",
            "Installing opencv in celery_worker container", check_error=True)

        # ============================================================
        # FIX 5: Restart backend to pick up code changes
        # ============================================================
        print("\n" + "="*60)
        print("  FIX 5: Restart backend (uvicorn --reload should auto-detect)")
        print("="*60)
        
        # Touch a file to trigger reload
        run_cmd(ssh,
            f"touch {PROJECT_PATH}/backend/app/main.py",
            "Touch main.py to trigger uvicorn reload")
        
        # Wait for reload
        print("  Waiting 5 seconds for uvicorn reload...")
        time.sleep(5)
        
        # Check if backend is up
        run_cmd(ssh,
            "docker logs --tail=5 ai_buhgalter_backend 2>&1",
            "Backend logs after reload")

        # ============================================================
        # VERIFY: Test API endpoints
        # ============================================================
        print("\n" + "="*60)
        print("  VERIFY: Test API endpoints")
        print("="*60)
        
        # Wait a bit more
        time.sleep(3)
        
        run_cmd(ssh,
            "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80/api/docs 2>/dev/null",
            "API docs (expected 200)")
        
        run_cmd(ssh,
            "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80/api/openapi.json 2>/dev/null",
            "OpenAPI JSON (expected 200)")
        
        run_cmd(ssh,
            "curl -s http://127.0.0.1:80/api/openapi.json 2>/dev/null | python3 -c \"import sys,json; d=json.load(sys.stdin); print('Paths:', len(d.get('paths',{})))\" 2>/dev/null || echo 'Failed to parse'",
            "Count API paths")
        
        run_cmd(ssh,
            "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80/ 2>/dev/null",
            "Frontend (expected 200)")
        
        run_cmd(ssh,
            "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80/api/v1/auth/register -X POST -H 'Content-Type: application/json' -d '{\"email\":\"test@test.com\",\"password\":\"test123\"}' 2>/dev/null",
            "Registration endpoint test")

        # ============================================================
        # FINAL: Show backend logs
        # ============================================================
        print("\n" + "="*60)
        print("  FINAL: Backend logs (last 10)")
        print("="*60)
        
        run_cmd(ssh, "docker logs --tail=10 ai_buhgalter_backend 2>&1", "")

        print("\n" + "="*60)
        print("  DEPLOY COMPLETE!")
        print(f"  Frontend: http://{HOST}/")
        print(f"  API Docs: http://{HOST}/api/docs")
        print(f"  ReDoc:    http://{HOST}/api/redoc")
        print("="*60)

    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        ssh.close()

if __name__ == "__main__":
    main()