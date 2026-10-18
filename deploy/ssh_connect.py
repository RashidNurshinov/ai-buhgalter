"""SSH connection to project server via paramiko"""
import os
import paramiko
import time

HOST = os.environ.get("DEPLOY_HOST", "")
USER = "root"
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "")
PROJECT_PATH = "/opt/ai-buhgalter"

def run_cmd(ssh, cmd, timeout=30):
    """Execute command and return output"""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print(f"Connecting to {HOST}...")
    for attempt in range(3):
        try:
            ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
            print("Connected successfully!\n")
            break
        except Exception as e:
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(5)
            else:
                print("Failed to connect after 3 attempts")
                return
    
    # 1. Check disk space
    print("=== Disk Space ===")
    out, _ = run_cmd(ssh, "df -h /")
    print(out)
    
    # 2. Check Docker containers
    print("=== Docker Containers ===")
    out, _ = run_cmd(ssh, f"cd {PROJECT_PATH} && docker ps --format 'table {{{{.Names}}}}\\t{{{{.Status}}}}\\t{{{{.Ports}}}}'")
    print(out)
    
    # 3. Check backend logs (last 20 lines)
    print("=== Backend Logs (last 20) ===")
    out, _ = run_cmd(ssh, "docker logs --tail=20 ai_buhgalter_backend 2>&1")
    print(out)
    
    # 4. Health check
    print("=== Health Check ===")
    out, _ = run_cmd(ssh, "curl -s http://localhost/api/health 2>&1 || echo 'Health check failed'")
    print(out)
    
    ssh.close()
    print("\nConnection closed.")

if __name__ == "__main__":
    main()
