# -*- coding: utf-8 -*-
import paramiko
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "138.124.108.144"
USER = "root"
PASSWORD = "jlGGd9v9cnhq"

def r(ssh, cmd):
    _, o, e = ssh.exec_command(cmd, timeout=60)
    return o.read().decode("utf-8", errors="replace"), e.read().decode("utf-8", errors="replace")

def p(text):
    print(text.encode("ascii", errors="replace").decode("ascii"))

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
    p("Connected")

    # 1. Full backend logs
    p("\n=== Backend ALL logs ===")
    out, _ = r(ssh, "docker logs ai_buhgalter_backend 2>&1")
    p(out.strip()[:3000])

    # 2. main.py startup/lifespan
    p("\n=== main.py (full) ===")
    out, _ = r(ssh, "cat /opt/ai-buhgalter/backend/app/main.py")
    p(out.strip()[:3000])

    # 3. Check if container is still running
    p("\n=== Container status ===")
    out, _ = r(ssh, "docker ps --filter name=backend --format '{{.Status}}'")
    p(out.strip())

    # 4. Try running python import directly inside container
    p("\n=== Test imports in container ===")
    out, _ = r(ssh, 'docker exec ai_buhgalter_backend python -c "print(1); from app.main import app; print(2, type(app))" 2>&1')
    p(out.strip()[:2000])

    # 5. Check schemas/__init__.py for broken imports
    p("\n=== schemas/__init__.py ===")
    out, _ = r(ssh, "cat /opt/ai-buhgalter/backend/app/schemas/__init__.py")
    p(out.strip()[:2000])

    # 6. Check if there's a circular import or missing module
    p("\n=== Test schema imports ===")
    out, _ = r(ssh, 'docker exec ai_buhgalter_backend python -c "from app.schemas import *; print(\"OK\")" 2>&1')
    p(out.strip()[:1000])

    ssh.close()
    p("\nDone.")

if __name__ == "__main__":
    main()