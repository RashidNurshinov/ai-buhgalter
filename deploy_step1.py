"""Step 1: Test connection and prepare server."""
import paramiko
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SERVER = "138.124.108.144"
USER = "root"
PASSWORD = "jlGGd9v9cnhq"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"Connecting to {SERVER}...")
client.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
print("Connected OK!")

# Server info
for cmd in ["uname -a", "df -h /", "free -m", "which docker", "docker --version 2>/dev/null || echo NO_DOCKER", "docker compose version 2>/dev/null || echo NO_COMPOSE"]:
    stdin, stdout, stderr = client.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    print(f"  {cmd}: {out}")

client.close()
print("DONE")