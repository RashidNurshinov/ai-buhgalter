import os
# -*- coding: utf-8 -*-
"""Debug startup by running uvicorn directly inside container."""
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

    # 1. Run a direct python startup test inside the container
    p("\n=== Direct lifespan test ===")
    out, _ = r(ssh, '''docker exec ai_buhgalter_backend python -c "
import asyncio

async def test():
    print('1. importing app...')
    from app.main import app, lifespan
    print('2. running lifespan...')
    async with lifespan(app) as state:
        print('3. lifespan yielded, state:', state)
    print('4. lifespan done')

asyncio.run(test())
" 2>&1''', timeout=30)
    p(out.strip()[:2000])

    # 2. Check .env file for potential issues
    p("\n=== .env DATABASE_URL ===")
    out, _ = r(ssh, "grep -E 'DATABASE_URL|REDIS_URL' /opt/ai-buhgalter/.env")
    p(out.strip())

    # 3. Check if DATABASE_URL uses correct hostname for docker
    p("\n=== Check config.settings ===")
    out, _ = r(ssh, '''docker exec ai_buhgalter_backend python -c "
from app.core.config import settings
print('DATABASE_URL:', settings.DATABASE_URL)
print('REDIS_URL:', settings.REDIS_URL)
print('APP_ENV:', settings.APP_ENV)
print('is_production:', settings.is_production)
print('is_development:', settings.is_development)
" 2>&1''')
    p(out.strip()[:500])

    # 4. Check strace for what's blocking
    p("\n=== Process info ===")
    out, _ = r(ssh, "docker exec ai_buhgalter_backend ps aux 2>&1")
    p(out.strip()[:500])

    # 5. Try running with --no-access-log and timeout 
    p("\n=== Try simple uvicorn test inside container ===")
    out, _ = r(ssh, '''docker exec ai_buhgalter_backend timeout 10 python -c "
import uvicorn
import asyncio
from app.main import app

# Test that app starts by running a single request
from starlette.testclient import TestClient
try:
    client = TestClient(app)
    r = client.get('/api/health')
    print('Health response:', r.status_code, r.json())
except Exception as e:
    print('Error:', e)
" 2>&1''', timeout=30)
    p(out.strip()[:2000])

    ssh.close()
    p("\nDone.")

if __name__ == "__main__":
    main()