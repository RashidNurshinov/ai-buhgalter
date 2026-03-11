# -*- coding: utf-8 -*-
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

    # 1. Check if the issue is --reload with volume mount
    # The old image had --reload but worked because the build COPY'd files
    # Now with volume mount, --reload may cause issues
    # Let's check by running without --reload via command override
    
    # Actually - the docker-compose.yml already has --reload
    # Let's check if the issue is that startup hangs
    # The log shows "Waiting for application startup" but no error
    # This means the lifespan generator yield never gets called
    
    # Check if redis is available
    p("\n=== Redis connectivity ===")
    out, _ = r(ssh, "docker exec ai_buhgalter_backend python -c \"import redis; c = redis.from_url('redis://redis:6379/0'); print(c.ping())\" 2>&1")
    p(out.strip())

    # Check if the issue is setup_logging hanging
    p("\n=== Test lifespan code manually ===")
    out, _ = r(ssh, '''docker exec ai_buhgalter_backend python -c "
from app.core.config import settings
print('settings OK:', settings.APP_NAME)
from app.core.logging import setup_logging
print('setup_logging imported')
setup_logging(log_level='INFO', json_output=True)
print('setup_logging called OK')
" 2>&1''')
    p(out.strip()[:1000])

    # Check if there is a DB migration issue
    p("\n=== Test DB connection ===")
    out, _ = r(ssh, '''docker exec ai_buhgalter_backend python -c "
from app.core.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    r = conn.execute(text('SELECT 1'))
    print('DB OK:', r.fetchone())
" 2>&1''')
    p(out.strip()[:500])

    # Look at middleware for issues
    p("\n=== Check middleware ===")
    out, _ = r(ssh, "cat /opt/ai-buhgalter/backend/app/core/middleware.py | head -50")
    p(out.strip()[:1500])

    # Try running uvicorn without --reload and check if it starts
    p("\n=== Try uvicorn without --reload ===")
    # Stop and restart with modified command
    r(ssh, "docker stop ai_buhgalter_backend 2>&1", timeout=15)
    time.sleep(2)
    
    # Run manually without --reload
    r(ssh, '''docker run -d --rm \
        --name ai_buhgalter_backend_test \
        --network docker_default \
        -v /opt/ai-buhgalter/backend:/app \
        -v /opt/ai-buhgalter/storage:/app/storage \
        --env-file /opt/ai-buhgalter/.env \
        docker-backend \
        uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 2>&1''')
    
    p("Waiting 15s for startup...")
    time.sleep(15)
    
    out, _ = r(ssh, "docker logs --tail=15 ai_buhgalter_backend_test 2>&1")
    p("\n=== Test container logs ===")
    p(out.strip()[:1500])

    out, _ = r(ssh, 'docker exec ai_buhgalter_nginx curl -s -o /dev/null -w "%{http_code}" http://ai_buhgalter_backend_test:8000/api/health 2>&1 || echo "Cannot reach"')
    p("Health check: " + out.strip())

    # Clean up test container and restart normal one
    r(ssh, "docker rm -f ai_buhgalter_backend_test 2>&1", timeout=10)
    
    # Start the real one back with compose
    out, _ = r(ssh, "cd /opt/ai-buhgalter/docker && docker compose up -d backend 2>&1")
    p("\nRestarted backend via compose: " + out.strip()[:200])
    
    p("\nWaiting 20s...")
    time.sleep(20)
    
    out, _ = r(ssh, "docker logs --tail=15 ai_buhgalter_backend 2>&1")
    p("\n=== Backend logs after restart ===")
    p(out.strip()[:1500])

    out, _ = r(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/health')
    p("Health: " + out.strip())

    ssh.close()
    p("\nDone.")

if __name__ == "__main__":
    main()