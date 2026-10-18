# -*- coding: utf-8 -*-
"""
Step 7: Deploy frontend/backend fixes to server.

Changes being deployed:
1. backend/app/schemas/base.py — removed duplicate PaginatedResponse
2. backend/app/schemas/files.py — switched to common.py imports
3. backend/app/api/v1/files.py — switched to common.py PaginatedResponse
4. backend/app/api/v1/agent.py — removed duplicate /agent/history endpoint
5. frontend/src/types/index.ts — added uploading/rejected to DocumentStatus
6. frontend/src/utils/format.ts — added uploading/rejected labels
7. frontend/src/pages/DocumentsPage.tsx — added uploading/rejected to filter & statusTag
8. frontend/src/api/endpoints.ts — PUT→POST for confirm, added reject
"""
import paramiko
import sys
import time
import os

HOST = os.environ.get("DEPLOY_HOST", "")
USER = "root"
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "")
PROJECT_PATH = "/opt/ai-buhgalter"

# Files to sync (local path relative to project root -> remote path)
FILES_TO_SYNC = [
    # Backend fixes
    ("backend/app/schemas/base.py", f"{PROJECT_PATH}/backend/app/schemas/base.py"),
    ("backend/app/schemas/files.py", f"{PROJECT_PATH}/backend/app/schemas/files.py"),
    ("backend/app/api/v1/files.py", f"{PROJECT_PATH}/backend/app/api/v1/files.py"),
    ("backend/app/api/v1/agent.py", f"{PROJECT_PATH}/backend/app/api/v1/agent.py"),
    # Frontend fixes
    ("frontend/src/types/index.ts", f"{PROJECT_PATH}/frontend/src/types/index.ts"),
    ("frontend/src/utils/format.ts", f"{PROJECT_PATH}/frontend/src/utils/format.ts"),
    ("frontend/src/pages/DocumentsPage.tsx", f"{PROJECT_PATH}/frontend/src/pages/DocumentsPage.tsx"),
    ("frontend/src/api/endpoints.ts", f"{PROJECT_PATH}/frontend/src/api/endpoints.ts"),
]


def run_cmd(ssh, cmd, desc="", timeout=120):
    if desc:
        print(f"\n--- {desc} ---")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if out.strip():
        # Limit output
        lines = out.strip().split('\n')
        for line in lines[:50]:
            print(f"  {line}")
        if len(lines) > 50:
            print(f"  ... ({len(lines) - 50} more lines)")
    if err.strip() and exit_code != 0:
        print(f"  [STDERR] {err.strip()[:2000]}")
    return out, err, exit_code


def upload_files(ssh):
    """Upload changed files to the server via SFTP."""
    sftp = ssh.open_sftp()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    uploaded = 0
    failed = 0
    
    for local_rel, remote_path in FILES_TO_SYNC:
        local_path = os.path.join(project_root, local_rel)
        if not os.path.exists(local_path):
            print(f"  [SKIP] {local_rel} — file not found locally")
            failed += 1
            continue
        
        try:
            # Ensure remote directory exists
            remote_dir = os.path.dirname(remote_path)
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                # Create directory recursively
                run_cmd(ssh, f"mkdir -p {remote_dir}")
            
            sftp.put(local_path, remote_path)
            file_size = os.path.getsize(local_path)
            print(f"  [OK] {local_rel} ({file_size} bytes) -> {remote_path}")
            uploaded += 1
        except Exception as e:
            print(f"  [FAIL] {local_rel}: {e}")
            failed += 1
    
    sftp.close()
    return uploaded, failed


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"Connecting to {HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
        print("[OK] Connected!\n")

        # ============================================================
        # Step 1: Check current state
        # ============================================================
        print("=" * 60)
        print("  STEP 1: Check current containers")
        print("=" * 60)
        
        run_cmd(ssh,
            "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null",
            "Running containers")

        # ============================================================
        # Step 2: Upload changed files
        # ============================================================
        print("\n" + "=" * 60)
        print("  STEP 2: Upload changed files")
        print("=" * 60)
        
        uploaded, failed = upload_files(ssh)
        print(f"\n  Uploaded: {uploaded}, Failed: {failed}")
        
        if failed > 0:
            print("  [WARN] Some files failed to upload!")

        # ============================================================
        # Step 3: Rebuild frontend
        # ============================================================
        print("\n" + "=" * 60)
        print("  STEP 3: Rebuild frontend")
        print("=" * 60)
        
        # Check if there's a docker-compose or separate build process
        run_cmd(ssh,
            f"ls {PROJECT_PATH}/docker/docker-compose*.yml 2>/dev/null || ls {PROJECT_PATH}/docker-compose*.yml 2>/dev/null",
            "Find docker-compose file")
        
        # Try to rebuild frontend container
        compose_file = None
        out, _, _ = run_cmd(ssh, f"ls {PROJECT_PATH}/docker/docker-compose.yml 2>/dev/null")
        if out.strip():
            compose_file = f"{PROJECT_PATH}/docker/docker-compose.yml"
        else:
            out, _, _ = run_cmd(ssh, f"ls {PROJECT_PATH}/docker-compose.yml 2>/dev/null")
            if out.strip():
                compose_file = f"{PROJECT_PATH}/docker-compose.yml"
        
        if compose_file:
            compose_dir = os.path.dirname(compose_file)
            
            # Rebuild frontend
            print("\n  Rebuilding frontend container (this may take a minute)...")
            run_cmd(ssh,
                f"cd {compose_dir} && docker compose build frontend 2>&1 | tail -20",
                "Build frontend", timeout=300)
            
            # Restart frontend
            run_cmd(ssh,
                f"cd {compose_dir} && docker compose up -d frontend 2>&1",
                "Restart frontend", timeout=60)
        else:
            # Alternative: maybe frontend is built inside nginx/frontend container
            print("  No docker-compose found, trying direct container restart...")
            run_cmd(ssh,
                "docker restart ai_buhgalter_frontend 2>/dev/null || echo 'No frontend container'",
                "Restart frontend container")

        # ============================================================
        # Step 4: Restart backend (to pick up Python changes)
        # ============================================================
        print("\n" + "=" * 60)
        print("  STEP 4: Restart backend")
        print("=" * 60)
        
        if compose_file:
            compose_dir = os.path.dirname(compose_file)
            run_cmd(ssh,
                f"cd {compose_dir} && docker compose restart backend 2>&1",
                "Restart backend", timeout=60)
        else:
            # Touch main.py for uvicorn --reload
            run_cmd(ssh,
                f"touch {PROJECT_PATH}/backend/app/main.py",
                "Touch main.py for uvicorn reload")
            
            # Also try docker restart
            run_cmd(ssh,
                "docker restart ai_buhgalter_backend 2>/dev/null || echo 'Trying uvicorn reload...'",
                "Restart backend container")
        
        # Wait for services to come up
        print("\n  Waiting 10 seconds for services to start...")
        time.sleep(10)

        # ============================================================
        # Step 5: Verify deployment
        # ============================================================
        print("\n" + "=" * 60)
        print("  STEP 5: Verify deployment")
        print("=" * 60)
        
        # Check container status
        run_cmd(ssh,
            "docker ps --format 'table {{.Names}}\t{{.Status}}' 2>/dev/null",
            "Container status")
        
        # Backend health
        run_cmd(ssh,
            "curl -s -o /dev/null -w 'HTTP %{http_code}' http://127.0.0.1:80/api/docs 2>/dev/null || echo 'FAIL'",
            "API Docs endpoint")
        
        run_cmd(ssh,
            "curl -s -o /dev/null -w 'HTTP %{http_code}' http://127.0.0.1:80/api/openapi.json 2>/dev/null || echo 'FAIL'",
            "OpenAPI JSON")
        
        # Frontend
        run_cmd(ssh,
            "curl -s -o /dev/null -w 'HTTP %{http_code}' http://127.0.0.1:80/ 2>/dev/null || echo 'FAIL'",
            "Frontend index")
        
        # Check backend logs for errors
        run_cmd(ssh,
            "docker logs --tail=15 ai_buhgalter_backend 2>&1",
            "Backend logs (last 15)")
        
        # Verify the /agent/history endpoint is gone (should return 404 or 405)
        run_cmd(ssh,
            "curl -s -o /dev/null -w 'HTTP %{http_code}' http://127.0.0.1:80/api/v1/agent/history 2>/dev/null",
            "Verify /agent/history removed (expect 401/404/405)")
        
        # Verify /agent/messages still works  
        run_cmd(ssh,
            "curl -s -o /dev/null -w 'HTTP %{http_code}' http://127.0.0.1:80/api/v1/agent/messages 2>/dev/null",
            "Verify /agent/messages exists (expect 401)")

        # ============================================================
        # DONE
        # ============================================================
        print("\n" + "=" * 60)
        print("  DEPLOY COMPLETE!")
        print(f"  Frontend: http://{HOST}/")
        print(f"  API Docs: http://{HOST}/api/docs")
        print(f"  ReDoc:    http://{HOST}/api/redoc")
        print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        ssh.close()


if __name__ == "__main__":
    main()