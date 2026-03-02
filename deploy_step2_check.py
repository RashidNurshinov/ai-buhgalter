"""Шаг 2: Проверить пересборку и тестировать."""
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

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    return stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')

# Проверяем лог пересборки
print('=== Rebuild log ===')
print(run('cat /tmp/rebuild.log 2>&1'))

# Статус контейнеров
print('\n=== Docker containers ===')
print(run('docker ps --format "table {{.Names}}\t{{.Status}}" 2>&1'))

# Логи backend
print('\n=== Backend logs (last 20) ===')
print(run('docker logs --tail=20 ai_buhgalter_backend 2>&1'))

# Тест регистрации
print('\n=== Test register ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"test_fix2@test.com","password":"test12345678","full_name":"Test Fix User 2"}' '''))

# Тест логина
print('\n=== Test login ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"test_fix2@test.com","password":"test12345678"}' '''))

ssh.close()
print('\nDone!')