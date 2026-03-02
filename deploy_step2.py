"""Step 2: Fix Dockerfile and rebuild."""
import paramiko
import sys
import time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SERVER = "138.124.108.144"
USER = "root"
PASSWORD = "jlGGd9v9cnhq"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"Connecting to {SERVER}...")
client.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
print("Connected!")

def run(cmd):
    print(f"\n>>> {cmd}")
    stdin, stdout, stderr = client.exec_command(cmd, timeout=600)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    code = stdout.channel.recv_exit_status()
    if out: print(out)
    if err and code != 0: print(f"ERR: {err}")
    elif err: print(err)
    return out, err, code

# Upload fixed Dockerfile
print("\n=== Uploading fixed Dockerfile ===")
sftp = client.open_sftp()
sftp.put("backend/Dockerfile", "/opt/ai-buhgalter/backend/Dockerfile")
sftp.close()
print("Dockerfile uploaded!")

# Verify the fix
print("\n=== Verifying Dockerfile on server ===")
run("cat /opt/ai-buhgalter/backend/Dockerfile")

# Clear docker build cache
print("\n=== Clearing Docker build cache ===")
run("docker builder prune -f 2>&1")

# Rebuild with --no-cache
print("\n=== Building containers with --no-cache (5-10 min) ===")
out, err, code = run("cd /opt/ai-buhgalter/docker && docker compose -f docker-compose.prod.yml build --no-cache 2>&1")

if code != 0:
    print(f"\n[!] Build failed with code {code}")
    client.close()
    exit(1)

print("\n=== Starting containers ===")
run("cd /opt/ai-buhgalter/docker && docker compose -f docker-compose.prod.yml up -d 2>&1")

print("\nWaiting 15 seconds for startup...")
time.sleep(15)

run("cd /opt/ai-buhgalter/docker && docker compose -f docker-compose.prod.yml ps")

# Migrations
print("\n=== Running migrations ===")
out, err, code = run("docker exec ai_buhgalter_backend alembic upgrade head 2>&1")
if code != 0:
    print("Migration failed, retrying in 10s...")
    time.sleep(10)
    run("docker exec ai_buhgalter_backend alembic upgrade head 2>&1")

# Health check
print("\n=== Health check ===")
time.sleep(5)
run("curl -s http://localhost/api/health")
run("curl -s -o /dev/null -w 'Frontend: %{http_code}' http://localhost/")

print("\n=== Backend logs ===")
run("docker logs ai_buhgalter_backend --tail 15 2>&1")

print(f"\n{'='*50}")
print(f"  DEPLOY COMPLETE!")
print(f"  URL: http://{SERVER}")
print(f"  API: http://{SERVER}/api/health")
print(f"{'='*50}")

client.close()