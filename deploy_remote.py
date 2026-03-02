"""
Скрипт деплоя ИИ-Бухгалтер на сервер через paramiko.
"""
import paramiko
import os
import sys
import time

# Фикс кодировки для Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SERVER = "138.124.108.144"
USER = "root"
PASSWORD = "jlGGd9v9cnhq"
REMOTE_DIR = "/opt/ai-buhgalter"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

EXCLUDE = {
    'node_modules', '__pycache__', '.git', '.env', 'venv', '.venv',
    'postgres_data', 'test_storage', '.mypy_cache', '.pytest_cache',
    '.ruff_cache', 'dist', 'build', '.idea', '.vscode',
    'deploy_remote.py', 'deploy.sh',
}

EXCLUDE_EXT = {'.pyc', '.pyo'}


def create_ssh_client():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"[*] Connecting to {SERVER}...")
    client.connect(SERVER, username=USER, password=PASSWORD, timeout=30)
    print("[+] Connected!")
    return client


def run_command(client, command, print_output=True):
    print(f"\n>>> {command}")
    stdin, stdout, stderr = client.exec_command(command, timeout=600)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    exit_code = stdout.channel.recv_exit_status()
    if print_output and out:
        print(out)
    if err:
        if exit_code != 0:
            print(f"STDERR: {err}")
        elif print_output:
            print(err)
    return out, err, exit_code


def upload_directory(sftp, local_dir, remote_dir):
    try:
        sftp.stat(remote_dir)
    except FileNotFoundError:
        sftp.mkdir(remote_dir)

    for item in os.listdir(local_dir):
        if item in EXCLUDE:
            continue
        local_path = os.path.join(local_dir, item)
        remote_path = f"{remote_dir}/{item}"

        if os.path.isfile(local_path):
            _, ext = os.path.splitext(item)
            if ext in EXCLUDE_EXT:
                continue
            try:
                sftp.put(local_path, remote_path)
            except Exception as e:
                print(f"  [!] Failed to upload {remote_path}: {e}")
        elif os.path.isdir(local_path):
            upload_directory(sftp, local_path, remote_path)


def count_files(local_dir):
    count = 0
    for root, dirs, files in os.walk(local_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE]
        for f in files:
            _, ext = os.path.splitext(f)
            if ext not in EXCLUDE_EXT:
                count += 1
    return count


def main():
    client = create_ssh_client()

    try:
        # === STEP 1: Server preparation ===
        print("\n" + "=" * 50)
        print("  STEP 1: Server preparation")
        print("=" * 50)

        run_command(client, "uname -a")
        run_command(client, "df -h / | grep -v Filesystem")
        run_command(client, "free -m | head -2")

        out, _, _ = run_command(client, "which docker 2>/dev/null", print_output=False)
        if not out.strip():
            print("\n[*] Installing Docker...")
            run_command(client, "apt-get update -qq && apt-get install -y -qq ca-certificates curl gnupg")
            run_command(client, "curl -fsSL https://get.docker.com | sh")
            run_command(client, "systemctl enable docker && systemctl start docker")
        else:
            print(f"[+] Docker already installed: {out.strip()}")

        run_command(client, "docker --version")

        out, _, code = run_command(client, "docker compose version 2>/dev/null", print_output=False)
        if code != 0:
            print("[*] Installing Docker Compose plugin...")
            run_command(client, "apt-get install -y -qq docker-compose-plugin")
        else:
            print(f"[+] Docker Compose: {out.strip()}")

        run_command(client, f"mkdir -p {REMOTE_DIR}")

        # === STEP 2: Upload files ===
        print("\n" + "=" * 50)
        print("  STEP 2: Upload files to server")
        print("=" * 50)

        total_files = count_files(PROJECT_DIR)
        print(f"[*] Files to upload: ~{total_files}")

        sftp = client.open_sftp()

        dirs_to_upload = ['backend', 'docker', 'frontend', 'storage', 'doc_project']
        files_to_upload = ['.env.example', '.gitignore', 'README.md']

        for d in dirs_to_upload:
            local = os.path.join(PROJECT_DIR, d)
            if os.path.exists(local):
                print(f"\n[*] Uploading {d}/...")
                upload_directory(sftp, local, f"{REMOTE_DIR}/{d}")
                print(f"  [+] {d}/ uploaded")

        for f in files_to_upload:
            local = os.path.join(PROJECT_DIR, f)
            if os.path.exists(local):
                print(f"[*] Uploading {f}...")
                sftp.put(local, f"{REMOTE_DIR}/{f}")

        sftp.close()
        print("\n[+] All files uploaded!")

        # === STEP 3: Setup .env ===
        print("\n" + "=" * 50)
        print("  STEP 3: Setup .env")
        print("=" * 50)

        out, _, _ = run_command(client, f"test -f {REMOTE_DIR}/.env && echo EXISTS || echo MISSING", print_output=False)

        if "MISSING" in out:
            print("[*] Creating .env from .env.example...")
            commands = f"""
cd {REMOTE_DIR}
cp .env.example .env

APP_SECRET=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)

sed -i "s|APP_ENV=development|APP_ENV=production|g" .env
sed -i "s|APP_DEBUG=true|APP_DEBUG=false|g" .env
sed -i "s|change-me-in-production-use-openssl-rand-hex-32|$APP_SECRET|g" .env
sed -i "s|change-me-jwt-secret-use-openssl-rand-hex-32|$JWT_SECRET|g" .env
sed -i "s|postgresql+asyncpg://postgres:postgres@localhost:5432/ai_buhgalter|postgresql+asyncpg://postgres:postgres@postgres:5432/ai_buhgalter|g" .env
sed -i "s|redis://localhost:6379/0|redis://redis:6379/0|g" .env
sed -i "s|redis://localhost:6379/1|redis://redis:6379/1|g" .env
sed -i "s|redis://localhost:6379/2|redis://redis:6379/2|g" .env
sed -i "s|APP_DOMAIN=localhost|APP_DOMAIN=138.124.108.144|g" .env

echo ".env created!"
grep -E "^(APP_ENV|APP_DEBUG|DATABASE_URL|REDIS_URL|APP_DOMAIN)" .env
"""
            run_command(client, commands)
        else:
            print("[+] .env already exists, skipping")
            run_command(client, f"grep -E '^(APP_ENV|DATABASE_URL|REDIS_URL)' {REMOTE_DIR}/.env")

        # === STEP 4: Build and start Docker ===
        print("\n" + "=" * 50)
        print("  STEP 4: Build Docker containers")
        print("  (this may take 5-10 minutes)")
        print("=" * 50)

        run_command(client, f"cd {REMOTE_DIR}/docker && docker compose -f docker-compose.prod.yml down 2>/dev/null || true")

        print("\n[*] Building containers...")
        out, err, code = run_command(client, f"cd {REMOTE_DIR}/docker && docker compose -f docker-compose.prod.yml build 2>&1")

        if code != 0:
            print(f"[!] Build error! Code: {code}")
            print(f"Output: {out}")
            print(f"Errors: {err}")
            return

        print("\n[*] Starting containers...")
        run_command(client, f"cd {REMOTE_DIR}/docker && docker compose -f docker-compose.prod.yml up -d")

        print("\n[*] Waiting for services to start (15 sec)...")
        time.sleep(15)

        run_command(client, f"cd {REMOTE_DIR}/docker && docker compose -f docker-compose.prod.yml ps")

        # === STEP 5: Database migrations ===
        print("\n" + "=" * 50)
        print("  STEP 5: Database migrations")
        print("=" * 50)

        out, err, code = run_command(client, "docker exec ai_buhgalter_backend alembic upgrade head 2>&1")

        if code != 0:
            print(f"[!] Migration error: {out}{err}")
            print("[*] Retrying in 10 seconds...")
            time.sleep(10)
            run_command(client, "docker exec ai_buhgalter_backend alembic upgrade head 2>&1")

        # === STEP 6: Verify ===
        print("\n" + "=" * 50)
        print("  STEP 6: Verify deployment")
        print("=" * 50)

        time.sleep(5)
        out, _, code = run_command(client, "curl -s http://localhost/api/health 2>&1")

        if '"status":"ok"' in out or '"status": "ok"' in out:
            print("[+] Backend API is working!")
        else:
            print(f"[!] API response: {out}")
            out2, _, _ = run_command(client, "curl -s http://localhost:8000/api/health 2>&1")
            print(f"[*] Direct backend: {out2}")

        out, _, code = run_command(client, "curl -s -o /dev/null -w '%{http_code}' http://localhost/ 2>&1")
        print(f"[*] Frontend HTTP status: {out}")

        print("\n[*] Backend logs (last 10 lines):")
        run_command(client, "docker logs ai_buhgalter_backend --tail 10 2>&1")

        print("\n" + "=" * 50)
        print("  [+] DEPLOY COMPLETE!")
        print(f"  URL: http://{SERVER}")
        print(f"  API: http://{SERVER}/api/health")
        print("=" * 50)

    except Exception as e:
        print(f"\n[!] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        client.close()
        print("\n[*] SSH connection closed.")


if __name__ == "__main__":
    main()