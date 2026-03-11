# -*- coding: utf-8 -*-
"""Quick verification after deploy."""
import paramiko
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"

HOST = "138.124.108.144"
USER = "root"
PASSWORD = "jlGGd9v9cnhq"

def run(ssh, cmd, desc=""):
    if desc:
        print(f"\n--- {desc} ---")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    # Replace non-ASCII for Windows console
    out = out.encode("ascii", errors="replace").decode("ascii")
    err = err.encode("ascii", errors="replace").decode("ascii")
    if out.strip():
        for line in out.strip().split("\n")[:60]:
            print(f"  {line}")
    if err.strip():
        for line in err.strip().split("\n")[:10]:
            print(f"  [err] {line}")
    return out


def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
    print(f"Connected to {HOST}")

    # Backend logs
    run(ssh, "docker logs --tail=30 ai_buhgalter_backend 2>&1", "Backend logs")

    # Direct backend test (port 8000 inside docker network)
    run(ssh,
        'docker exec ai_buhgalter_nginx curl -s -o /dev/null -w "%{http_code}" http://backend:8000/api/docs',
        "Backend /api/docs via docker network")

    run(ssh,
        'docker exec ai_buhgalter_nginx curl -s -o /dev/null -w "%{http_code}" http://backend:8000/api/v1/dashboard/',
        "Backend /api/v1/dashboard via docker network")

    # Via nginx port 80
    run(ssh,
        'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/v1/calendar/ 2>/dev/null',
        "Nginx -> Backend /api/v1/calendar/")

    run(ssh,
        'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/ 2>/dev/null',
        "Frontend /")

    # Check uploaded files on server
    run(ssh, "head -5 /opt/ai-buhgalter/backend/app/schemas/base.py", "base.py (first 5 lines)")
    run(ssh, "head -5 /opt/ai-buhgalter/backend/app/api/v1/agent.py", "agent.py (first 5 lines)")
    run(ssh, "head -3 /opt/ai-buhgalter/frontend/src/api/endpoints.ts", "endpoints.ts (first 3 lines)")

    # Check if agent/history route is gone
    run(ssh,
        'grep -n "history" /opt/ai-buhgalter/backend/app/api/v1/agent.py || echo "No history route found - OK"',
        "Verify /agent/history removed")

    # Check schemas/files.py on server
    run(ssh,
        'ls -la /opt/ai-buhgalter/backend/app/schemas/files.py 2>/dev/null || echo "NOT FOUND (expected - no local file)"',
        "schemas/files.py on server")

    # Check frontend build
    run(ssh, "docker logs --tail=10 ai_buhgalter_frontend 2>&1", "Frontend container logs")

    ssh.close()
    print("\n=== Verification complete ===")


if __name__ == "__main__":
    main()