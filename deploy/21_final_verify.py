import os
# -*- coding: utf-8 -*-
"""Final verification: all endpoints, tests, and deployment health."""
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
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    return out, err

def p(text):
    print(text.encode("ascii", errors="replace").decode("ascii"))

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
    p("=" * 60)
    p("FINAL DEPLOYMENT VERIFICATION")
    p("=" * 60)

    # 1. Container status
    p("\n--- Container Status ---")
    out, _ = r(ssh, "docker ps --format 'table {{.Names}}\t{{.Status}}' | sort")
    p(out.strip())

    # 2. API Health
    p("\n--- API Health ---")
    out, _ = r(ssh, 'curl -s http://127.0.0.1:80/api/health')
    p(out.strip())

    # 3. Swagger docs
    p("\n--- Swagger Docs ---")
    out, _ = r(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/api/docs')
    p(f"Docs status: {out.strip()}")

    # 4. OpenAPI schema validation
    p("\n--- OpenAPI Schema ---")
    out, _ = r(ssh, 'curl -s http://127.0.0.1:80/api/openapi.json | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\\"Title: {d[\'info\'][\'title\']}, Paths: {len(d[\'paths\'])}\\"); [print(f\\"  {m.upper()} {p}\\") for p,v in sorted(d[\'paths\'].items()) for m in v.keys()][:30]" 2>&1')
    p(out.strip()[:2000])

    # 5. Frontend
    p("\n--- Frontend ---")
    out, _ = r(ssh, 'curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:80/')
    p(f"Frontend status: {out.strip()}")

    # 6. Register test user
    p("\n--- Register Test User ---")
    out, _ = r(ssh, '''curl -s http://127.0.0.1:80/api/v1/auth/register -X POST -H "Content-Type: application/json" -d '{"email":"final_test@test.com","password":"TestPass123!","full_name":"Test User","inn":"1234567890","tax_system":"usn_income"}' ''')
    p(out.strip()[:300])

    # 7. Login test
    p("\n--- Login Test ---")
    out, _ = r(ssh, '''curl -s http://127.0.0.1:80/api/v1/auth/login -X POST -H "Content-Type: application/json" -d '{"email":"final_test@test.com","password":"TestPass123!"}' ''')
    login_resp = out.strip()
    p(login_resp[:300])

    # Extract token
    import json
    try:
        token_data = json.loads(login_resp)
        token = token_data.get("access_token", "")
        if token:
            p(f"\nToken obtained: {token[:30]}...")
            
            # 8. Test authenticated endpoints
            p("\n--- Authenticated Endpoints ---")
            auth_header = f'Authorization: Bearer {token}'
            
            endpoints = [
                ("GET /api/v1/users/me", f'curl -s -w "\\n%{{http_code}}" http://127.0.0.1:80/api/v1/users/me -H "{auth_header}"'),
                ("GET /api/v1/documents", f'curl -s -w "\\n%{{http_code}}" http://127.0.0.1:80/api/v1/documents -H "{auth_header}"'),
                ("GET /api/v1/bank-operations", f'curl -s -w "\\n%{{http_code}}" http://127.0.0.1:80/api/v1/bank-operations -H "{auth_header}"'),
                ("GET /api/v1/counterparties", f'curl -s -w "\\n%{{http_code}}" http://127.0.0.1:80/api/v1/counterparties -H "{auth_header}"'),
                ("GET /api/v1/dashboard", f'curl -s -w "\\n%{{http_code}}" http://127.0.0.1:80/api/v1/dashboard -H "{auth_header}"'),
                ("GET /api/v1/tax-calendar", f'curl -s -w "\\n%{{http_code}}" http://127.0.0.1:80/api/v1/tax-calendar -H "{auth_header}"'),
            ]
            for name, cmd in endpoints:
                out, _ = r(ssh, cmd)
                lines = out.strip().split('\n')
                status = lines[-1] if lines else '?'
                body = '\n'.join(lines[:-1])[:100] if len(lines) > 1 else ''
                p(f"  {name}: {status} {body}")
    except json.JSONDecodeError:
        p("Could not parse login response")

    # 9. Run unit tests inside container
    p("\n--- Unit Tests ---")
    out, _ = r(ssh, 'docker exec ai_buhgalter_backend python -m pytest tests/ -x -q --tb=short 2>&1', timeout=120)
    p(out.strip()[:3000])

    p("\n" + "=" * 60)
    p("VERIFICATION COMPLETE")
    p("=" * 60)

    ssh.close()

if __name__ == "__main__":
    main()