# -*- coding: utf-8 -*-
"""Rebuild backend container to pick up file changes and verify."""
import paramiko
import time
import sys
import os

HOST = "138.124.108.144"
USER = "root"
PASSWORD = "jlGGd9v9cnhq"
PROJECT_PATH = "/opt/ai-buhgalter"
COMPOSE_DIR = f"{PROJECT_PATH}/docker"

def run(ssh, cmd, desc="", timeout=180):
    if desc:
        print(f"\n--- {desc} ---")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    # ASCII-safe for Windows console
    out_safe = out.encode("ascii", errors="replace").decode("ascii")
    err_safe = err.encode("ascii", errors="replace").decode("ascii")
    if out_safe.strip():
        for line in out_safe.strip().split("\n")[:60]:
            print(f"  {line}")
    if err_safe.strip():
        for line in err_safe.strip().split("\n")[:20]:
            print(f"  [log] {line}")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
    print(f"Connected to {HOST}")

    # Step 1: Check that volume mount exists (../backend:/app)
    run(ssh,
        f'grep -A 5 "volumes" {COMPOSE_DIR}/docker-compose.yml | grep backend',
        "Check backend volume mount in compose")

    # The docker-compose.yml has "../backend:/app" volume mount
    # But docker inspect shows only storage mount
    # This means the container was recreated without the volume
    # Let's force recreate with volumes

    # Step 2: Rebuild and recreate backend with --force-recreate
    print("\n=== Rebuilding backend container ===")
    run(ssh,
        f"cd {COMPOSE_DIR} && docker compose up -d --force-recreate --build backend 2>&1 | tail -30",
        "Rebuild backend", timeout=300)

    # Step 3: Wait for backend to start
    print("\n  Waiting 15 seconds for backend to start...")
    time.sleep(15)

    # Step 4: Verify backend mount
    run(ssh,
        'docker inspect ai_buhgalter_backend --format "{{json .Mounts}}" | python3 -m json.tool',
        "Backend mounts after rebuild")

    # Step 5: Check if files are there
    run(ssh,
        'docker exec ai_buhgalter_backend head -5 /app/app/schemas/base.py',
        "base.py inside container")
    
    run(ssh,
        'docker exec ai_buhgalter_backend python -c "from app.schemas.common import PaginatedResponse; print(list(PaginatedResponse.model_fields.keys()))"',
        "PaginatedResponse fields")

    # Step 6: Check backend logs after restart
    run(ssh,
        "docker logs --tail=20 ai_buhgalter_backend 2>&1",
        "Backend logs after rebuild")

    # Step 7: Test endpoints
    run(ssh,
        'curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1:80/api/docs',
        "GET /api/docs")

    run(ssh,
        'curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1:80/api/openapi.json',
        "GET /api/openapi.json")

    run(ssh,
        'curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1:80/',
        "GET / (frontend)")

    # Test with auth token - register a test user
    run(ssh,
        '''curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1:80/api/v1/auth/register -X POST -H "Content-Type: application/json" -d '{"email":"deploy_test@test.com","password":"Test1234!","full_name":"Deploy Test"}\'''',
        "POST /auth/register")

    # Try login
    run(ssh,
        '''curl -s http://127.0.0.1:80/api/v1/auth/login -X POST -H "Content-Type: application/json" -d '{"email":"deploy_test@test.com","password":"Test1234!"}\'''',
        "POST /auth/login")

    # Step 8: Also rebuild celery_worker since it uses same code
    print("\n=== Rebuilding celery worker ===")
    run(ssh,
        f"cd {COMPOSE_DIR} && docker compose up -d --force-recreate celery_worker celery_beat 2>&1 | tail -10",
        "Rebuild celery worker & beat", timeout=120)

    # Final status
    run(ssh,
        "docker ps --format 'table {{.Names}}\t{{.Status}}'",
        "Final container status")

    ssh.close()
    print("\n=== Rebuild and verification complete ===")
    print(f"Frontend: http://{HOST}/")
    print(f"API Docs: http://{HOST}/api/docs")

if __name__ == "__main__":
    main()