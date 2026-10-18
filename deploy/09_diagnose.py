import os
# -*- coding: utf-8 -*-
import paramiko
import sys

HOST = os.environ.get("DEPLOY_HOST", "")
USER = "root"
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "")

def run(ssh, cmd):
    _, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)

    results = []

    # 1. docker-compose backend section
    out, err = run(ssh, "cat /opt/ai-buhgalter/docker/docker-compose.yml")
    results.append("=== docker-compose.yml ===")
    results.append(out[:3000])

    # 2. documents.py PaginatedResponse
    out, err = run(ssh, 'grep -n "PaginatedResponse\|skip\|limit\|page\|per_page" /opt/ai-buhgalter/backend/app/api/v1/documents.py')
    results.append("\n=== documents.py grep ===")
    results.append(out[:2000])

    # 3. PaginatedResponse in container
    out, err = run(ssh, 'docker exec ai_buhgalter_backend python -c "from app.schemas.common import PaginatedResponse; print(list(PaginatedResponse.model_fields.keys()))"')
    results.append("\n=== PaginatedResponse fields in container ===")
    results.append(out + err)

    # 4. Check main.py docs settings
    out, err = run(ssh, 'grep -n "docs_url\|redoc_url\|openapi_url" /opt/ai-buhgalter/backend/app/main.py')
    results.append("\n=== main.py docs settings ===")
    results.append(out[:1000])

    # 5. Check if files are mounted as volumes or copied
    out, err = run(ssh, 'docker inspect ai_buhgalter_backend --format "{{json .Mounts}}" 2>/dev/null | python3 -m json.tool 2>/dev/null || docker inspect ai_buhgalter_backend --format "{{json .Mounts}}"')
    results.append("\n=== Backend mounts ===")
    results.append(out[:2000])

    ssh.close()

    # Write to file to avoid encoding issues
    with open("deploy/diagnose_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(results))
    
    # Also print ASCII-safe version
    full = "\n".join(results)
    print(full.encode("ascii", errors="replace").decode("ascii"))

if __name__ == "__main__":
    main()