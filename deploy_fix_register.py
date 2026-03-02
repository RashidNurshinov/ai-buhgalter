"""Скрипт для деплоя исправления регистрации на сервер."""
import paramiko
import sys
import io
import time
import socket

# Фиксим кодировку для Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def connect_ssh(retries=3):
    for attempt in range(retries):
        try:
            print(f'SSH connect attempt {attempt + 1}...')
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Увеличенные таймауты
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
            return ssh
        except Exception as e:
            print(f'Attempt {attempt + 1} failed: {e}')
            if attempt < retries - 1:
                time.sleep(5)
            else:
                raise

ssh = connect_ssh()

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    return out + err

sftp = ssh.open_sftp()

# Загружаем исправленные файлы
files_to_upload = [
    ('backend/app/models/user.py', '/opt/ai-buhgalter/backend/app/models/user.py'),
    ('backend/app/services/auth_service.py', '/opt/ai-buhgalter/backend/app/services/auth_service.py'),
    ('backend/app/api/v1/auth.py', '/opt/ai-buhgalter/backend/app/api/v1/auth.py'),
]

for local_path, remote_path in files_to_upload:
    sftp.put(local_path, remote_path)
    print(f'Uploaded {local_path} -> {remote_path}')

sftp.close()

# Проверяем ключевые строки
print('\n=== Verify auth_service.py register ===')
print(run('grep -n "register\\|TokenResponse\\|return" /opt/ai-buhgalter/backend/app/services/auth_service.py'))

print('\n=== Verify auth.py register ===')
print(run('grep -n "register\\|response_model\\|TokenResponse" /opt/ai-buhgalter/backend/app/api/v1/auth.py'))

print('\n=== Verify user.py tax_system ===')
print(run('grep -n "tax_system\\|values_callable" /opt/ai-buhgalter/backend/app/models/user.py'))

# Пересобираем и перезапускаем backend
print('\n=== Rebuilding backend container ===')
print(run('cd /opt/ai-buhgalter/docker && docker compose up -d --build backend 2>&1'))

# Ждём запуска
print('Waiting 15s for container startup...')
time.sleep(15)

# Проверяем статус
print('\n=== Container status ===')
print(run('docker ps --filter "name=ai_buhgalter_backend"'))

# Проверяем логи
print('\n=== Backend logs (last 10 lines) ===')
print(run('docker logs --tail=10 ai_buhgalter_backend 2>&1'))

# Тестируем регистрацию
print('\n=== Test register ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"test_fix@test.com","password":"test12345678","full_name":"Test Fix User"}' '''))

ssh.close()
print('\nDone!')