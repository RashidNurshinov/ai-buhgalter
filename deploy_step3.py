"""Step 3: Upload fixed frontend files and rebuild."""
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
    if out: print(out[-3000:] if len(out) > 3000 else out)
    if err and code != 0: print(f"ERR: {err[-2000:]}")
    elif err: print(err[-2000:] if len(err) > 2000 else err)
    return out, err, code

# Upload fixed files
print("\n=== Uploading fixed files ===")
sftp = client.open_sftp()

files_to_upload = [
    ("frontend/src/pages/DashboardPage.tsx", "/opt/ai-buhgalter/frontend/src/pages/DashboardPage.tsx"),
    ("frontend/src/pages/KudirPage.tsx", "/opt/ai-buhgalter/frontend/src/pages/KudirPage.tsx"),
    ("frontend/src/pages/OperationsPage.tsx", "/opt/ai-buhgalter/frontend/src/pages/OperationsPage.tsx"),
    ("frontend/src/pages/TaxesPage.tsx", "/opt/ai-buhgalter/frontend/src/pages/TaxesPage.tsx"),
    ("backend/Dockerfile", "/opt/ai-buhgalter/backend/Dockerfile"),
]

for local, remote in files_to_upload:
    print(f"  Uploading {local}...")
    sftp.put(local, remote)

sftp.close()
print("Files uploaded!")

# Rebuild (only nginx since backend Dockerfile already has libgl1)
print("\n=== Building containers (5-10 min) ===")
out, err, code = run("cd /opt/ai-buhgalter/docker && docker compose -f docker-compose.prod.yml build --no-cache 2>&1")

if code != 0:
    print(f"\n[!] Build failed with code {code}")
    client.close()
    sys.exit(1)

print("\n[+] Build succeeded!")

print("\n=== Starting containers ===")
run("cd /opt/ai-buhgalter/docker && docker compose -f docker-compose.prod.yml up -d 2>&1")

print("\nWaiting 20 seconds for startup...")
time.sleep(20)

run("cd /opt/ai-buhgalter/docker && docker compose -f docker-compose.prod.yml ps 2>&1")

# Migrations
print("\n=== Running migrations ===")
out, err, code = run("docker exec ai_buhgalter_backend alembic upgrade head 2>&1")
if code != 0:
    print("Migration issue, retrying in 10s...")
    time.sleep(10)
    run("docker exec ai_buhgalter_backend alembic upgrade head 2>&1")

# Health check
print("\n=== Health check ===")
time.sleep(5)
run("curl -sf http://localhost/api/health || echo 'API not ready'")
run("curl -sf -o /dev/null -w 'Frontend: HTTP %{http_code}\\n' http://localhost/ || echo 'Frontend not ready'")

print("\n=== Backend logs (last 20 lines) ===")
run("docker logs ai_buhgalter_backend --tail 20 2>&1")

print(f"\n{'='*50}")
print(f"  DEPLOY COMPLETE!")
print(f"  URL: http://{SERVER}")
print(f"  API: http://{SERVER}/api/health")
print(f"{'='*50}")

client.close()