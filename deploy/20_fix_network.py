# -*- coding: utf-8 -*-
"""Fix Docker networking - nginx not on same network as backend."""
import paramiko
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = "138.124.108.144"
USER = "root"
PASSWORD = "jlGGd9v9cnhq"

def r(ssh, cmd, timeout=30):
    _, o, e = ssh.exec_command(cmd, timeout=timeout)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    return out, err

def p(text):
    print(text.encode("ascii", errors="replace").decode("ascii"))

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
    p("Connected")

    # 1. Check nginx network membership
    p("\n=== Nginx networks ===")
    out, _ = r(ssh, "docker inspect ai_buhgalter_nginx --format '{{json .NetworkSettings.Networks}}' 2>&1")
    p(out.strip()[:500])

    # 2. Check backend network membership
    p("\n=== Backend networks ===")
    out, _ = r(ssh, "docker inspect ai_buhgalter_backend --format '{{json .NetworkSettings.Networks}}' 2>&1")
    p(out.strip()[:500])

    # 3. Check docker-compose for nginx service definition
    p("\n=== Nginx in docker-compose ===")
    out, _ = r(ssh, "grep -A 30 'nginx:' /opt/ai-buhgalter/docker/docker-compose.yml | head -35")
    p(out.strip())

    # 4. The fix: bring everything down and up together
    p("\n=== Full restart: docker compose down + up ===")
    out, _ = r(ssh, "cd /opt/ai-buhgalter/docker && docker compose down 2>&1", timeout=60)
    p("Down: " + out.strip()[:500])
    
    time.sleep(5)
    
    out, _ = r(ssh, "cd /opt/ai-buhgalter/docker && docker compose up -d 2>&1", timeout=120)
    p("Up: " + out.strip()[:800])

    p("\nWaiting 25s for all services to start...")
    time.sleep(25)

    # 5. Check all containers
    p("\n=== Container status ===")
    out, _ = r(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}' | sort")
    p(out.strip())

    # 6. Check network
    p("\n=== Network members ===")
    out, _ = r(ssh, "docker network inspect docker_default --format '{{range .Containers}}{{.Name}}: {{.IPv4Address}}; {{end}}' 2>&1")
    p(out.strip()[:500])

    # 7. Backend logs
    out, _ = r(ssh, "docker logs --tail=10 ai_buhgalter_backend 2>&1")
    p("\n=== Backend logs ===")
    p(out.strip()[:500])

    # 8. Test endpoints
    p("\n=== Test endpoints ===")
    out, _ = r(ssh, 'curl -s --connect-timeout 5 http://127.0.0.1:80/api/health 2>&1')
    p("/api/health: " + out.strip()[:200])
    
    out, _ = r(ssh, 'curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://127.0.0.1:80/api/docs 2>&1')
    p("/api/docs: " + out.strip())
    
    out, _ = r(ssh, 'curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 http://127.0.0.1:80/ 2>&1')
    p("/: " + out.strip())

    # 9. Login test
    p("\n=== Login test ===")
    out, _ = r(ssh, '''curl -s --connect-timeout 5 http://127.0.0.1:80/api/v1/auth/login -X POST -H "Content-Type: application/json" -d '{"email":"test@test.com","password":"Test1234!"}' 2>&1''')
    p(out.strip()[:300])

    ssh.close()
    p("\nDone.")

if __name__ == "__main__":
    main()