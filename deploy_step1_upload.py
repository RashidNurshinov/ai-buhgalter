"""Шаг 1: Загрузка файлов на сервер."""
import paramiko
import sys
import io
import socket

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(60)
sock.connect(('138.124.108.144', 22))

ssh.connect(
    '138.124.108.144',
    username='root',
    password='jlGGd9v9cnhq',
    timeout=60,
    banner_timeout=120,
    auth_timeout=60,
    sock=sock,
)
print('Connected!')

sftp = ssh.open_sftp()

files_to_upload = [
    ('backend/app/models/user.py', '/opt/ai-buhgalter/backend/app/models/user.py'),
    ('backend/app/services/auth_service.py', '/opt/ai-buhgalter/backend/app/services/auth_service.py'),
    ('backend/app/api/v1/auth.py', '/opt/ai-buhgalter/backend/app/api/v1/auth.py'),
    ('backend/app/constants/enums.py', '/opt/ai-buhgalter/backend/app/constants/enums.py'),
]

for local_path, remote_path in files_to_upload:
    sftp.put(local_path, remote_path)
    print(f'Uploaded {local_path} -> {remote_path}')

sftp.close()

# Verify uploaded files
def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    return stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')

print('\n=== Verify user.py has values_callable ===')
print(run('grep -n "values_callable" /opt/ai-buhgalter/backend/app/models/user.py'))

print('\n=== Start rebuild in background (nohup) ===')
# Запуск пересборки в background - не ждём завершен��я
stdin, stdout, stderr = ssh.exec_command(
    'nohup bash -c "cd /opt/ai-buhgalter/docker && docker compose up -d --build backend" > /tmp/rebuild.log 2>&1 &',
    timeout=10,
)
print('Rebuild started in background. Check /tmp/rebuild.log on server.')

ssh.close()
print('\nDone! Run deploy_step2_check.py in ~60s to verify.')