"""Шаг 6: Убрать маппинг портов 5432 наружу для postgres (vpn_postgres занимает)."""
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

# 1. Заменить ports на expose для postgres тоже
print('=== Fix docker-compose.yml - postgres ports -> expose ===')
print(run(r'''
cd /opt/ai-buhgalter/docker && python3 << 'PYEOF'
with open('docker-compose.yml', 'r') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    # Заменяем ports: "5432:5432" на expose: "5432" в секции postgres
    if line.strip() == 'ports:' and i+1 < len(lines) and '"5432:5432"' in lines[i+1]:
        new_lines.append(line.replace('ports:', 'expose:'))
        new_lines.append(lines[i+1].replace('"5432:5432"', '"5432"'))
        i += 2
        continue
    # Заменяем ports: "6379:6379" на expose: "6379" в секции redis
    elif line.strip() == 'ports:' and i+1 < len(lines) and '"6379:6379"' in lines[i+1]:
        new_lines.append(line.replace('ports:', 'expose:'))
        new_lines.append(lines[i+1].replace('"6379:6379"', '"6379"'))
        i += 2
        continue
    # Заменяем ports: "3000:3000" на expose: "3000" в секции frontend
    elif line.strip() == 'ports:' and i+1 < len(lines) and '"3000:3000"' in lines[i+1]:
        new_lines.append(line.replace('ports:', 'expose:'))
        new_lines.append(lines[i+1].replace('"3000:3000"', '"3000"'))
        i += 2
        continue
    new_lines.append(line)
    i += 1

with open('docker-compose.yml', 'w') as f:
    f.writelines(new_lines)
print('Fixed all ports -> expose!')
PYEOF
'''))

# 2. Показать итоговый compose
print('\n=== Full docker-compose.yml (ports/expose lines) ===')
print(run('grep -n -E "(ports:|expose:|5432|6379|8000|3000)" /opt/ai-buhgalter/docker/docker-compose.yml'))

# 3. Остановить все наши контейнеры и запустить заново
print('\n=== Docker compose down + up ===')
print(run('cd /opt/ai-buhgalter/docker && docker compose down 2>&1', timeout=30))

time.sleep(3)

print(run('cd /opt/ai-buhgalter/docker && docker compose up -d 2>&1', timeout=60))

time.sleep(10)

# 4. Проверка
print('\n=== Docker ps ===')
print(run('docker ps --format "table {{.Names}}\t{{.Status}}" | grep buhgalter'))

print('\n=== Backend logs ===')
print(run('docker logs --tail=40 ai_buhgalter_backend 2>&1'))

# 5. Тест через nginx
print('\n=== Test register via nginx ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"testfix6@test.com","password":"test12345678","full_name":"Test Fix6"}' '''))

ssh.close()
print('\nDone!')