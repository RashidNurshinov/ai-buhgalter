import os
# -*- coding: utf-8 -*-
"""
Step 3: Deep check - compare local vs server code, find issues
"""
import paramiko
import sys

HOST = os.environ.get("DEPLOY_HOST", "")
USER = "root"
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "")
PROJECT_PATH = "/opt/ai-buhgalter"

def run_cmd(ssh, cmd, desc=""):
    if desc:
        print(f"\n{'='*60}")
        print(f"  {desc}")
        print(f"{'='*60}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    out_safe = out.encode('ascii', errors='replace').decode('ascii')
    err_safe = err.encode('ascii', errors='replace').decode('ascii')
    if out_safe.strip():
        print(out_safe)
    if err_safe.strip():
        print(f"[STDERR] {err_safe}")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
        print("[OK] Connected!")

        # Check endpoints directory - it showed empty
        run_cmd(ssh, f"find {PROJECT_PATH}/backend/app/api -type f -name '*.py' | sort", "All API files on server")
        
        # Check router.py content
        run_cmd(ssh, f"cat {PROJECT_PATH}/backend/app/api/v1/router.py 2>/dev/null || echo 'FILE NOT FOUND'", "router.py content")
        
        # Check main.py
        run_cmd(ssh, f"cat {PROJECT_PATH}/backend/app/main.py 2>/dev/null | head -50", "main.py (first 50 lines)")
        
        # Check TaxCalendarEvent model - find the 'deadline' field
        run_cmd(ssh, f"cat {PROJECT_PATH}/backend/app/models/tax_calendar_event.py 2>/dev/null", "TaxCalendarEvent model")
        
        # Check agent_tools for 'deadline' reference
        run_cmd(ssh, f"grep -n 'deadline' {PROJECT_PATH}/backend/app/services/agent_tools.py 2>/dev/null", "agent_tools.py - 'deadline' references")
        
        # Check agent_event model
        run_cmd(ssh, f"cat {PROJECT_PATH}/backend/app/models/agent_event.py 2>/dev/null", "AgentEvent model")
        
        # Check Dockerfile
        run_cmd(ssh, f"cat {PROJECT_PATH}/backend/Dockerfile 2>/dev/null", "Backend Dockerfile")
        
        # Check requirements.txt for cv2
        run_cmd(ssh, f"grep -i 'cv2\\|opencv' {PROJECT_PATH}/backend/requirements.txt 2>/dev/null || echo 'opencv NOT in requirements'", "opencv in requirements.txt")
        
        # Check docker-compose.yml
        run_cmd(ssh, f"cat {PROJECT_PATH}/docker/docker-compose.yml 2>/dev/null", "docker-compose.yml")
        
        # Check nginx config
        run_cmd(ssh, f"cat {PROJECT_PATH}/docker/nginx/default.conf 2>/dev/null || cat {PROJECT_PATH}/docker/nginx/nginx.conf 2>/dev/null", "Nginx config")

        print("\n[DONE] Deep check complete.")

    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    finally:
        ssh.close()

if __name__ == "__main__":
    main()