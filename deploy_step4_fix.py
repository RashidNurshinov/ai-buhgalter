"""
Шаг 4: Исправление ошибки UserSettings и пересборка backend.
"""
import paramiko
import os

HOST = "138.124.108.144"
USER = "root"
PASSWORD = "jlGGd9v9cnhq"
PROJECT_DIR = "/root/ai_buhgalter"

def ssh_exec(ssh, cmd, timeout=300):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors='replace')
    err = stderr.read().decode(errors='replace')
    if out.strip():
        print(out[-2000:] if len(out) > 2000 else out)
    if err.strip():
        print(f"STDERR: {err[-1000:]}")
    return out, err

def upload_file(ssh, local_path, remote_path):
    """Upload a single file via SFTP."""
    sftp = ssh.open_sftp()
    print(f"Uploading {local_path} -> {remote_path}")
    sftp.put(local_path, remote_path)
    sftp.close()

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
    
    # Upload fixed users.py
    upload_file(ssh, 
                "backend/app/api/v1/users.py", 
                f"{PROJECT_DIR}/backend/app/api/v1/users.py")
    
    # Rebuild and restart only backend
    print("\n=== Rebuilding backend ===")
    ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose build backend", timeout=600)
    
    print("\n=== Restarting backend ===")
    ssh_exec(ssh, f"cd {PROJECT_DIR} && docker compose up -d backend")
    
    # Wait for startup
    import time
    time.sleep(10)
    
    # Check health
    print("\n=== Health check ===")
    ssh_exec(ssh, "curl -sf http://localhost/api/health || echo 'API not ready'")
    
    # Check backend logs
    print("\n=== Backend logs ===")
    ssh_exec(ssh, "docker logs ai_buhgalter_backend --tail 30 2>&1")
    
    ssh.close()
    print("\nDone!")

if __name__ == "__main__":
    main()