# -*- coding: utf-8 -*-
"""Fix backend startup hang - likely due to lifespan or watchfiles issue."""
import paramiko
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "138.124.108.144"
USER = "root"
PASSWORD = "jlGGd9v9cnhq"

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

    # The problem: backend shows "Waiting for application startup" forever
    # This means lifespan async generator never reaches yield
    # But we tested setup_logging manually and it works
    # The issue is likely the database/alembic init that happens during import
    
    # Let's check if there's a database.py startup issue
    p("\n=== Check database.py for startup hooks ===")
    out, _ = r(ssh, "cat /opt/ai-buhgalter/backend/app/core/database.py")
    p(out.strip()[:2000])

    # Check if there's an async init_db or create_tables
    p("\n=== Check for init_db/create_tables patterns ===")
    out, _ = r(ssh, "grep -rn 'init_db\\|create_all\\|create_tables\\|startup\\|on_event' /opt/ai-buhgalter/backend/app/ --include='*.py' | head -20")
    p(out.strip()[:1000])

    # Check alembic config - maybe it runs on startup
    p("\n=== Check alembic env.py ===")
    out, _ = r(ssh, "head -30 /opt/ai-buhgalter/backend/alembic/env.py")
    p(out.strip()[:1000])

    # The real fix: let's look at whether the backend was ever working with volume mount
    # before our changes. Check git log on server
    p("\n=== Git status on server ===")
    out, _ = r(ssh, "cd /opt/ai-buhgalter && git log --oneline -5 2>&1")
    p(out.strip())
    
    out, _ = r(ssh, "cd /opt/ai-buhgalter && git diff --stat HEAD 2>&1")
    p(out.strip()[:1000])

    # Let's see what files were changed
    p("\n=== Changed files ===")
    out, _ = r(ssh, "cd /opt/ai-buhgalter && git diff --name-only 2>&1")
    p(out.strip()[:500])

    # Key insight: backend startup was working BEFORE our rebuild
    # The old container used cached image where code was COPY'd
    # Now after rebuild, it picks up our changed files via volume mount
    # Something in our changes may have broken startup
    # BUT - the test showed "from app.main import app" works fine!
    # The lifespan itself should work too (we tested setup_logging)
    
    # Wait - maybe it's a redis connection issue at startup?
    p("\n=== Check close_redis / redis.py ===")
    out, _ = r(ssh, "cat /opt/ai-buhgalter/backend/app/core/redis.py")
    p(out.strip()[:1500])

    # Let's try a simpler approach: just restart the container 
    # (the old code still works, our code changes are fine)
    # The issue might be that during rebuild the reloader triggered multiple times
    
    p("\n=== Force stop and start fresh ===")
    out, _ = r(ssh, "cd /opt/ai-buhgalter/docker && docker compose down backend 2>&1")
    p(out.strip()[:500])
    time.sleep(3)
    
    out, _ = r(ssh, "cd /opt/ai-buhgalter/docker && docker compose up -d backend 2>&1")
    p(out.strip()[:500])
    
    p("\nWaiting 30s for startup...")
    time.sleep(30)
    
    out, _ = r(ssh, "docker logs --tail=30 ai_buhgalter_backend 2>&1")
    p("\n=== Logs after fresh start ===")
    p(out.strip()[:2000])
    
    out, _ = r(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/health')
    p("\nHealth: " + out.strip())
    
    out, _ = r(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/docs')
    p("Docs: " + out.strip())

    ssh.close()
    p("\nDone.")

if __name__ == "__main__":
    main()