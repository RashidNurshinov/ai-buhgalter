import os
# -*- coding: utf-8 -*-
"""Fix backend --reload issue: switch to production mode without --reload."""
import paramiko
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = os.environ.get("DEPLOY_HOST", "")
USER = "root"
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "")

def r(ssh, cmd, timeout=60):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    return o.read().decode("utf-8", errors="replace"), e.read().decode("utf-8", errors="replace")

def p(text):
    print(text.encode("ascii", errors="replace").decode("ascii"))

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
    p("Connected")

    # 1. Check current docker-compose backend command
    p("\n=== Current docker-compose backend section ===")
    out, _ = r(ssh, "grep -A 20 'backend:' /opt/ai-buhgalter/docker/docker-compose.yml | head -25")
    p(out.strip())

    # 2. Check Dockerfile CMD
    p("\n=== Dockerfile CMD ===")
    out, _ = r(ssh, "grep -E 'CMD|ENTRYPOINT' /opt/ai-buhgalter/backend/Dockerfile")
    p(out.strip())

    # 3. Fix: change the command in docker-compose.yml to not use --reload
    # Replace --reload with --workers 2 for production
    p("\n=== Fixing docker-compose.yml ===")
    
    # First check current command line
    out, _ = r(ssh, "grep 'reload' /opt/ai-buhgalter/docker/docker-compose.yml")
    p("Current reload setting: " + out.strip())
    
    # Replace --reload with --workers 2
    r(ssh, r"""sed -i 's/--reload/--workers 2/' /opt/ai-buhgalter/docker/docker-compose.yml""")
    
    out, _ = r(ssh, "grep -A 2 'command.*uvicorn' /opt/ai-buhgalter/docker/docker-compose.yml")
    p("After fix: " + out.strip())

    # 4. Restart backend
    p("\n=== Restart backend ===")
    out, _ = r(ssh, "cd /opt/ai-buhgalter/docker && docker compose up -d --force-recreate backend 2>&1")
    p(out.strip()[:500])
    
    p("\nWaiting 15s...")
    time.sleep(15)
    
    # 5. Check logs
    out, _ = r(ssh, "docker logs --tail=20 ai_buhgalter_backend 2>&1")
    p("\n=== Backend logs ===")
    p(out.strip()[:1500])

    # 6. Test endpoints
    p("\n=== Test endpoints ===")
    endpoints = [
        "http://127.0.0.1:80/api/health",
        "http://127.0.0.1:80/api/docs",
        "http://127.0.0.1:80/api/openapi.json",
        "http://127.0.0.1:80/",
    ]
    for url in endpoints:
        out, _ = r(ssh, f'curl -s -o /dev/null -w "%{{http_code}}" {url}')
        p(f"  {url.split('80')[1]}: {out.strip()}")

    # 7. Test login  
    p("\n=== Login test ===")
    out, _ = r(ssh, '''curl -s http://127.0.0.1:80/api/v1/auth/login -X POST -H "Content-Type: application/json" -d '{"email":"deploy_test@test.com","password":"Test1234!"}' ''')
    p(out.strip()[:300])

    # 8. Also restart celery workers (they use same code)
    p("\n=== Restart celery ===")
    out, _ = r(ssh, "cd /opt/ai-buhgalter/docker && docker compose restart celery_worker celery_beat 2>&1")
    p(out.strip()[:300])

    # 9. Final status
    time.sleep(3)
    p("\n=== Final container status ===")
    out, _ = r(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}' | sort")
    p(out.strip())

    ssh.close()
    p("\nDone.")

if __name__ == "__main__":
    main()