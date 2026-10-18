# -*- coding: utf-8 -*-
"""
Step 1: Server diagnostics
"""
import paramiko
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"

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
    if out.strip():
        print(out)
    if err.strip():
        print(f"[STDERR] {err}")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to {HOST}...")
        ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
        print("[OK] Connected!")
        
        run_cmd(ssh, "uname -a", "OS")
        run_cmd(ssh, "cat /etc/os-release | head -5", "Distro")
        run_cmd(ssh, "free -h | head -3", "Memory")
        run_cmd(ssh, "df -h / | tail -1", "Disk")
        run_cmd(ssh, "nproc", "CPU cores")
        
        run_cmd(ssh, "docker --version 2>/dev/null || echo 'Docker NOT installed'", "Docker")
        run_cmd(ssh, "docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo 'Docker Compose NOT installed'", "Docker Compose")
        
        run_cmd(ssh, "docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || echo 'No containers'", "Containers")
        
        run_cmd(ssh, f"ls -la {PROJECT_PATH}/ 2>/dev/null || echo 'Directory {PROJECT_PATH} NOT found'", "Project dir")
        run_cmd(ssh, f"ls -la {PROJECT_PATH}/.env 2>/dev/null || echo '.env NOT found'", ".env file")
        run_cmd(ssh, f"ls {PROJECT_PATH}/docker/ 2>/dev/null || echo 'docker/ dir NOT found'", "Docker configs")
        
        run_cmd(ssh, "ss -tlnp | grep -E ':(80|443|8000|5432|6379|3000)' || echo 'Ports are free'", "Used ports")
        
        run_cmd(ssh, "git --version 2>/dev/null || echo 'Git NOT installed'", "Git")
        
        print("\n[DONE] Diagnostics complete.")
        
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    finally:
        ssh.close()

if __name__ == "__main__":
    main()