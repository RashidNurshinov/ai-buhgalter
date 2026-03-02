"""Шаг 5: Правильно починить docker-compose.yml и запустить всё."""
import paramiko
import sys
import io
import socket
import time

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

# 1. Исправить docker-compose.yml: expose: "8000" (не "8000:8000")  
# Nginx общается по docker network, порт наружу не нужен
print('=== Fix docker-compose.yml ===')
print(run(r'''
cd /opt/ai-buhgalter/docker && python3 -c "
with open('docker-compose.yml', 'r') as f:
    content = f.read()

# Заменяем expose: с неправильным форматом на правильный
content = content.replace('    expose:\n      - \"8000:8000\"', '    expose:\n      - \"8000\"')

with open('docker-compose.yml', 'w') as f:
    f.write(content)
print('Fixed!')
"
'''))

# Проверяем
print('\n=== Backend section now ===')
print(run('sed -n "/backend:/,/celery_worker:/p" /opt/ai-buhgalter/docker/docker-compose.yml | head -25'))

# 2. Убить всё что на порту 8000
print('\n=== Kill port 8000 ===')
print(run('fuser -k 8000/tcp 2>/dev/null; echo "done"'))
time.sleep(1)

# 3. Проверим что на 5432 тоже всё ок
print('\n=== Port 5432 status ===')
print(run('ss -tlnp | grep 5432'))

# 4. Перезапустить backend + postgres
print('\n=== Docker compose up ===')
print(run('cd /opt/ai-buhgalter/docker && docker compose up -d --force-recreate backend postgres 2>&1', timeout=60))

time.sleep(8)

# 5. Проверка
print('\n=== Docker ps ===')
print(run('docker ps --format "table {{.Names}}\t{{.Status}}" | grep buhgalter'))

print('\n=== Backend logs ===')
print(run('docker logs --tail=40 ai_buhgalter_backend 2>&1'))

# 6. Тест
print('\n=== Test register ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"testfix5@test.com","password":"test12345678","full_name":"Test Fix5"}' '''))

ssh.close()
print('\nDone!')