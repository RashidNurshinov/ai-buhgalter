"""Шаг 4: Починить backend (п��рт 8000 конфликт)."""
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

# Что на порту 8000
print('=== What uses port 8000? ===')
print(run('ss -tlnp | grep 8000'))

# Убить процесс на 8000
print('\n=== Kill process on 8000 ===')
print(run('fuser -k 8000/tcp 2>/dev/null; echo "done"'))
time.sleep(2)

# Проверить docker-compose.yml - какие порты маппятся
print('\n=== Docker compose ports config ===')
print(run('grep -A5 "ports:" /opt/ai-buhgalter/docker/docker-compose.yml'))

# Убрать маппинг порта 8000 наружу (nginx общается по docker network)
# Изменим ports на expose для backend
print('\n=== Fix docker-compose: remove port 8000 mapping for backend ===')
# Заменяем ports: - "8000:8000" на expose: - "8000" для backend
run('''cd /opt/ai-buhgalter/docker && python3 -c "
import re
with open('docker-compose.yml', 'r') as f:
    content = f.read()

# Заменяем маппинг порта 8000 на expose
# Найдём секцию backend и заменим ports на expose
content = content.replace('      - \"8000:8000\"', '      - \"8000\"')

# Проверим что нет двойного ports у backend, заменим на expose 
# Нужна более точная замена - в секции backend
lines = content.split('\\n')
in_backend = False
fixed = []
for i, line in enumerate(lines):
    if line.strip().startswith('backend:'):
        in_backend = True
    elif line.strip() and not line.startswith(' ') and not line.startswith('#'):
        if ':' in line and not line.startswith(' '):
            in_backend = False
    
    if in_backend and line.strip() == 'ports:':
        # Check next line is 8000
        if i+1 < len(lines) and '8000' in lines[i+1]:
            fixed.append(line.replace('ports:', 'expose:'))
            continue
    fixed.append(line)

with open('docker-compose.yml', 'w') as f:
    f.write('\\n'.join(fixed))
print('Fixed!')
"
''')

# Показать что получилось
print('\n=== Backend section in docker-compose.yml ===')
print(run('sed -n "/backend:/,/^  [a-z]/p" /opt/ai-buhgalter/docker/docker-compose.yml | head -30'))

# Перезапуск только backend
print('\n=== Restart backend ===')
print(run('cd /opt/ai-buhgalter/docker && docker compose up -d backend 2>&1', timeout=60))

time.sleep(5)

# Проверка
print('\n=== Docker ps ===')
print(run('docker ps --format "table {{.Names}}\t{{.Status}}" | grep buhgalter'))

print('\n=== Backend logs ===')
print(run('docker logs --tail=30 ai_buhgalter_backend 2>&1'))

# Тест
print('\n=== Test register ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"testfix4@test.com","password":"test12345678","full_name":"Test Fix4"}' '''))

ssh.close()
print('\nDone!')