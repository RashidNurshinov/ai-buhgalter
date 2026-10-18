import os
# -*- coding: utf-8 -*-
"""Fix nginx->backend connectivity by restarting nginx and checking config."""
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

    # 1. Check nginx config for upstream
    p("\n=== Nginx config ===")
    out, _ = r(ssh, "cat /opt/ai-buhgalter/docker/nginx/nginx.conf")
    p(out.strip()[:2000])

    # 2. Check what networks containers are on
    p("\n=== Container networks ===")
    out, _ = r(ssh, "docker network inspect docker_default --format '{{range .Containers}}{{.Name}}: {{.IPv4Address}}; {{end}}' 2>&1")
    p(out.strip()[:500])

    # 3. Check if nginx can resolve 'backend'
    p("\n=== Nginx DNS resolution ===")
    out, _ = r(ssh, "docker exec ai_buhgalter_nginx getent hosts backend 2>&1 || echo 'getent not found'")
    p("getent: " + out.strip())
    
    out, _ = r(ssh, "docker exec ai_buhgalter_nginx nslookup backend 2>&1 || echo 'nslookup not found'")
    p("nslookup: " + out.strip()[:200])

    # 4. Try with curl from nginx using IP
    out, _ = r(ssh, "docker inspect ai_buhgalter_backend --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'")
    backend_ip = out.strip()
    p(f"\nBackend IP: {backend_ip}")
    
    out, _ = r(ssh, f'docker exec ai_buhgalter_nginx curl -s http://{backend_ip}:8000/api/health 2>&1')
    p(f"nginx->IP direct: {out.strip()[:200]}")

    # 5. Check nginx upstream config - it likely uses 'backend' hostname
    # The issue: nginx resolves DNS at startup and caches it
    # When backend container restarts, it gets a new IP but nginx doesn't re-resolve
    
    # Fix: restart nginx
    p("\n=== Restart nginx ===")
    out, _ = r(ssh, "cd /opt/ai-buhgalter/docker && docker compose restart nginx 2>&1")
    p(out.strip()[:300])
    
    time.sleep(5)

    # 6. Test again
    p("\n=== Test after nginx restart ===")
    out, _ = r(ssh, 'curl -s http://127.0.0.1:80/api/health')
    p("/api/health: " + out.strip()[:200])

    out, _ = r(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/docs')
    p("/api/docs: " + out.strip())

    out, _ = r(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/')
    p("/: " + out.strip())

    # 7. Test login
    p("\n=== Login test ===")
    out, _ = r(ssh, '''curl -s http://127.0.0.1:80/api/v1/auth/login -X POST -H "Content-Type: application/json" -d '{"email":"deploy_test@test.com","password":"Test1234!"}' ''')
    p(out.strip()[:300])

    # 8. Full status
    p("\n=== All containers ===")
    out, _ = r(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}' | sort")
    p(out.strip())

    ssh.close()
    p("\nDone.")

if __name__ == "__main__":
    main()