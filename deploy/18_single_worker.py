import os
# -*- coding: utf-8 -*-
"""Fix: run uvicorn with single worker, no reload."""
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

    # 1. Fix: use single worker, no --reload, no --workers
    p("\n=== Fix docker-compose command ===")
    out, _ = r(ssh, "grep 'command.*uvicorn' /opt/ai-buhgalter/docker/docker-compose.yml")
    p("Before: " + out.strip())
    
    # Replace the entire command line
    r(ssh, r"""sed -i 's|command: uvicorn.*|command: uvicorn app.main:app --host 0.0.0.0 --port 8000|' /opt/ai-buhgalter/docker/docker-compose.yml""")
    
    out, _ = r(ssh, "grep 'command.*uvicorn' /opt/ai-buhgalter/docker/docker-compose.yml")
    p("After: " + out.strip())

    # 2. Restart
    p("\n=== Recreate backend ===")
    out, _ = r(ssh, "cd /opt/ai-buhgalter/docker && docker compose up -d --force-recreate backend 2>&1")
    p(out.strip()[:500])
    
    p("\nWaiting 20s...")
    time.sleep(20)

    # 3. Check logs
    out, _ = r(ssh, "docker logs --tail=15 ai_buhgalter_backend 2>&1")
    p("\n=== Backend logs ===")
    p(out.strip()[:1500])

    # 4. Test
    p("\n=== Test endpoints ===")
    tests = [
        ("/api/health", 'curl -s http://127.0.0.1:80/api/health'),
        ("/api/docs", 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/docs'),
        ("/api/openapi.json", 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/openapi.json'),
        ("/", 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/'),
    ]
    for name, cmd in tests:
        out, _ = r(ssh, cmd)
        p(f"  {name}: {out.strip()[:200]}")

    # 5. If still 502, try direct curl to backend:8000
    p("\n=== Direct backend test (bypass nginx) ===")
    out, _ = r(ssh, 'docker exec ai_buhgalter_nginx curl -s http://backend:8000/api/health 2>&1 || echo "FAIL"')
    p("nginx->backend: " + out.strip()[:200])
    
    # Also test from host directly to container
    out, _ = r(ssh, "docker inspect ai_buhgalter_backend --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'")
    ip = out.strip()
    p(f"Backend IP: {ip}")
    if ip:
        out, _ = r(ssh, f'curl -s --connect-timeout 5 http://{ip}:8000/api/health')
        p(f"Direct to {ip}:8000: " + out.strip()[:200])

    ssh.close()
    p("\nDone.")

if __name__ == "__main__":
    main()