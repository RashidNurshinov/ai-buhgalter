"""Шаг 3: Починить запуск контейнеров (порт 5432 конфликт)."""
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

def run(cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')

# Проверяем что занимает порт 5432
print('=== What uses port 5432? ===')
print(run('ss -tlnp | grep 5432'))

# Останавливаем системный postgres если запущен
print('\n=== Stop system postgres ===')
print(run('systemctl stop postgresql 2>/dev/null; systemctl disable postgresql 2>/dev/null; echo "done"'))

# Убиваем процесс на порту
print('\n=== Kill process on 5432 ===')
print(run('fuser -k 5432/tcp 2>/dev/null; echo "done"'))

# Проверяем порт после
print('\n=== Port 5432 after kill ===')
print(run('ss -tlnp | grep 5432'))

# Перезапускаем все контейнеры
print('\n=== Restart containers ===')
print(run('cd /opt/ai-buhgalter/docker && docker compose up -d 2>&1', timeout=60))

# Ждём старта
import time
time.sleep(5)

# Проверяем статус
print('\n=== Docker status ===')
print(run('docker ps --format "table {{.Names}}\t{{.Status}}"'))

# Логи backend
print('\n=== Backend logs ===')
print(run('docker logs --tail=30 ai_buhgalter_backend 2>&1'))

# Тест регистрации
print('\n=== Test register ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"testfix3@test.com","password":"test12345678","full_name":"Test Fix3"}' '''))

ssh.close()
print('\nDone!')