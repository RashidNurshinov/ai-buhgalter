import os
# -*- coding: utf-8 -*-
import paramiko
import time
import sys
import io

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = os.environ.get("DEPLOY_HOST", "")
USER = "root"
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "")

def r(ssh, cmd):
    _, o, e = ssh.exec_command(cmd, timeout=60)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    return out, err

def p(text):
    """Print ASCII-safe."""
    safe = text.encode("ascii", errors="replace").decode("ascii")
    print(safe)

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
    p("Connected")

    # 1. Fix requirements.txt
    p("\n=== Fix requirements.txt ===")
    out, _ = r(ssh, "grep -n 'opencv' /opt/ai-buhgalter/backend/requirements.txt")
    p("Before: " + out.strip())
    
    r(ssh, "sed -i 's/ruff==0.8.6opencv/ruff==0.8.6\\nopencv/' /opt/ai-buhgalter/backend/requirements.txt")
    
    out, _ = r(ssh, "sed -n '64,68p' /opt/ai-buhgalter/backend/requirements.txt")
    p("After lines 64-68:\n" + out.strip())

    # 2. Check main.py docs config
    p("\n=== main.py docs ===")
    out, _ = r(ssh, "grep -n 'docs_url\\|openapi_url\\|redoc_url' /opt/ai-buhgalter/backend/app/main.py")
    p(out.strip())

    # 3. Check base.py content (should NOT have old PaginatedResponse)
    p("\n=== base.py on server ===")
    out, _ = r(ssh, "cat /opt/ai-buhgalter/backend/app/schemas/base.py")
    p(out.strip()[:500])

    # 4. Rebuild backend image and restart
    p("\n=== Rebuild backend ===")
    out, err = r(ssh, "cd /opt/ai-buhgalter/docker && docker compose build backend 2>&1 | tail -15")
    p((out + err).strip()[:1000])
    
    p("\n=== Recreate backend ===")
    out, err = r(ssh, "cd /opt/ai-buhgalter/docker && docker compose up -d --force-recreate backend 2>&1")
    p((out + err).strip()[:500])

    p("\nWaiting 12s...")
    time.sleep(12)

    # 5. Check logs
    p("\n=== Backend logs ===")
    out, _ = r(ssh, "docker logs --tail=15 ai_buhgalter_backend 2>&1")
    p(out.strip()[:1500])

    # 6. Test endpoints
    p("\n=== Test endpoints ===")
    out, _ = r(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/docs')
    p("/api/docs: " + out.strip())
    
    out, _ = r(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/openapi.json')
    p("/api/openapi.json: " + out.strip())
    
    out, _ = r(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/')
    p("/ (frontend): " + out.strip())

    # 7. Check backend mounts
    p("\n=== Backend mounts ===")
    out, _ = r(ssh, 'docker inspect ai_buhgalter_backend --format "{{range .Mounts}}{{.Source}} -> {{.Destination}}; {{end}}"')
    p(out.strip())

    # 8. Check base.py INSIDE container
    p("\n=== base.py INSIDE container ===")
    out, _ = r(ssh, "docker exec ai_buhgalter_backend cat /app/app/schemas/base.py")
    p(out.strip()[:500])

    ssh.close()
    p("\nDone.")

if __name__ == "__main__":
    main()