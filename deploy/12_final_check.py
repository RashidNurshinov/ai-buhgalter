import os
# -*- coding: utf-8 -*-
import paramiko
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

HOST = os.environ.get("DEPLOY_HOST", "")
USER = "root"
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "")

def r(ssh, cmd):
    _, o, e = ssh.exec_command(cmd, timeout=60)
    return o.read().decode("utf-8", errors="replace"), e.read().decode("utf-8", errors="replace")

def p(text):
    print(text.encode("ascii", errors="replace").decode("ascii"))

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
    p("Connected. Waiting 25s for backend startup...")
    time.sleep(25)

    # Backend logs
    p("\n=== Backend logs (last 20) ===")
    out, _ = r(ssh, "docker logs --tail=20 ai_buhgalter_backend 2>&1")
    p(out.strip()[:2000])

    # Test all endpoints
    p("\n=== Endpoint tests ===")
    
    endpoints = [
        ("GET /api/docs", 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/docs'),
        ("GET /api/openapi.json", 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/openapi.json'),
        ("GET /api/redoc", 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/redoc'),
        ("GET / (frontend)", 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/'),
        ("GET /api/v1/auth/me", 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/v1/auth/me'),
        ("GET /api/v1/documents/", 'curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer test" http://127.0.0.1:80/api/v1/documents/'),
        ("GET /api/v1/files/", 'curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer test" http://127.0.0.1:80/api/v1/files/'),
        ("GET /api/v1/agent/messages", 'curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer test" http://127.0.0.1:80/api/v1/agent/messages'),
    ]
    
    for name, cmd in endpoints:
        out, _ = r(ssh, cmd)
        p(f"  {name}: {out.strip()}")

    # Login and test with real token
    p("\n=== Test with real token ===")
    out, _ = r(ssh, '''curl -s http://127.0.0.1:80/api/v1/auth/login -X POST -H "Content-Type: application/json" -d '{"email":"deploy_test@test.com","password":"Test1234!"}' ''')
    p("Login response: " + out.strip()[:200])
    
    # Extract token
    import json
    try:
        data = json.loads(out)
        token = data.get("access_token", "")
        if token:
            p(f"Token: {token[:30]}...")
            
            # Test with real token
            auth_endpoints = [
                ("GET /api/v1/documents/", f'curl -s -w "\\nHTTP %{{http_code}}" http://127.0.0.1:80/api/v1/documents/ -H "Authorization: Bearer {token}"'),
                ("GET /api/v1/files/", f'curl -s -w "\\nHTTP %{{http_code}}" http://127.0.0.1:80/api/v1/files/ -H "Authorization: Bearer {token}"'),
                ("GET /api/v1/agent/messages", f'curl -s -w "\\nHTTP %{{http_code}}" http://127.0.0.1:80/api/v1/agent/messages?limit=5 -H "Authorization: Bearer {token}"'),
                ("GET /api/v1/dashboard/summary", f'curl -s -w "\\nHTTP %{{http_code}}" http://127.0.0.1:80/api/v1/dashboard/summary -H "Authorization: Bearer {token}"'),
            ]
            
            for name, cmd in auth_endpoints:
                out, _ = r(ssh, cmd)
                lines = out.strip().split("\n")
                status = lines[-1] if lines else "?"
                body = "\n".join(lines[:-1])[:200]
                p(f"\n  {name}: {status}")
                p(f"    Body: {body}")
    except:
        p("  Could not parse login response")

    ssh.close()
    p("\n=== Final check complete ===")

if __name__ == "__main__":
    main()