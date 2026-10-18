import os
# -*- coding: utf-8 -*-
"""
Step 2: Check app health - backend logs, API response, frontend, DB state
"""
import paramiko
import sys

HOST = os.environ.get("DEPLOY_HOST", "")
USER = "root"
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "")
PROJECT_PATH = "/opt/ai-buhgalter"

def run_cmd(ssh, cmd, desc=""):
    if desc:
        print(f"\n{'='*60}")
        print(f"  {desc}")
        print(f"{'='*60}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    # Remove non-ASCII chars for Windows cp1251 compatibility
    out_safe = out.encode('ascii', errors='replace').decode('ascii')
    err_safe = err.encode('ascii', errors='replace').decode('ascii')
    if out_safe.strip():
        print(out_safe)
    if err_safe.strip():
        print(f"[STDERR] {err_safe}")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"Connecting to {HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
        print("[OK] Connected!")

        # Backend logs
        run_cmd(ssh, "docker logs --tail=40 ai_buhgalter_backend 2>&1", "Backend logs (last 40)")

        # Celery worker logs
        run_cmd(ssh, "docker logs --tail=15 ai_buhgalter_celery_worker 2>&1", "Celery worker logs")

        # Celery beat logs
        run_cmd(ssh, "docker logs --tail=10 ai_buhgalter_celery_beat 2>&1", "Celery beat logs")

        # Nginx logs
        run_cmd(ssh, "docker logs --tail=10 ai_buhgalter_nginx 2>&1", "Nginx logs")

        # Test API health via docker network
        run_cmd(ssh, "docker exec ai_buhgalter_nginx curl -s -o /dev/null -w '%{http_code}' http://backend:8000/docs 2>/dev/null || echo 'unreachable'", "API docs via nginx->backend")

        # Test via localhost
        run_cmd(ssh, "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80/ 2>/dev/null || echo 'unreachable'", "Frontend via nginx (HTTP code)")
        run_cmd(ssh, "curl -s http://127.0.0.1:80/ 2>/dev/null | head -5", "Frontend HTML (first 5 lines)")
        run_cmd(ssh, "curl -s http://127.0.0.1:80/api/v1/docs 2>/dev/null | head -3 || echo 'API docs unreachable'", "API docs response")

        # DB tables
        run_cmd(ssh, "docker exec ai_buhgalter_postgres psql -U postgres -d ai_buhgalter -c '\\dt' 2>&1 || echo 'DB not accessible'", "Database tables")

        # Check alembic
        run_cmd(ssh, "docker exec ai_buhgalter_backend alembic current 2>&1", "Alembic current migration")

        # Check .env on server (mask secrets)
        run_cmd(ssh, f"cat {PROJECT_PATH}/.env 2>/dev/null | sed 's/=.*/=***/' | head -30", "Server .env keys (masked)")

        # Backend files
        run_cmd(ssh, f"find {PROJECT_PATH}/backend/app -name '*.py' | wc -l", "Backend Python files count")
        run_cmd(ssh, f"ls {PROJECT_PATH}/backend/app/api/v1/endpoints/ 2>/dev/null", "Backend endpoints on server")
        run_cmd(ssh, f"ls {PROJECT_PATH}/backend/app/services/ 2>/dev/null", "Backend services on server")
        run_cmd(ssh, f"ls {PROJECT_PATH}/backend/app/models/ 2>/dev/null", "Backend models on server")

        # Frontend files
        run_cmd(ssh, f"find {PROJECT_PATH}/frontend/src -name '*.tsx' -o -name '*.ts' | wc -l", "Frontend TS/TSX files count")
        run_cmd(ssh, f"ls {PROJECT_PATH}/frontend/src/pages/ 2>/dev/null", "Frontend pages on server")

        print("\n[DONE] Health check complete.")

    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    finally:
        ssh.close()

if __name__ == "__main__":
    main()