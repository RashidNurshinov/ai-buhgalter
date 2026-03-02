"""Шаг 10b: Исправить SQLAlchemy Enum — использовать values вместо names."""
import paramiko
import sys
import io
import socket
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def connect_ssh(retries=3):
    for attempt in range(retries):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(60)
            sock.connect(('138.124.108.144', 22))
            ssh.connect('138.124.108.144', username='root', password='jlGGd9v9cnhq',
                       timeout=60, banner_timeout=120, auth_timeout=60, sock=sock)
            return ssh
        except Exception as e:
            print(f'Attempt {attempt+1} failed: {e}')
            time.sleep(5)
    raise Exception('Failed to connect')

time.sleep(5)
ssh = connect_ssh()
print('Connected!')

def run(cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')

# 1. Посмотреть enums.py
print('=== constants/enums.py ===')
print(run('cat /opt/ai-buhgalter/backend/app/constants/enums.py'))

# 2. Исправить модель User — добавить values_callable чтобы SQLAlchemy использовал .value
# SQLAlchemy Enum(TaxSystem) по умолчанию использует .name для создания enum values
# Нужно: Enum(TaxSystem, values_callable=lambda x: [e.value for e in x])
print('\n=== Fix User model ===')
print(run(r'''
cd /opt/ai-buhgalter/backend && python3 << 'PYEOF'
with open('app/models/user.py', 'r') as f:
    content = f.read()

# Заменяем Enum(TaxSystem, name="tax_system_enum") на версию с values_callable
old = 'Enum(TaxSystem, name="tax_system_enum")'
new = 'Enum(TaxSystem, name="tax_system_enum", values_callable=lambda x: [e.value for e in x])'

if old in content and new not in content:
    content = content.replace(old, new)
    with open('app/models/user.py', 'w') as f:
        f.write(content)
    print('Fixed: added values_callable to TaxSystem Enum')
else:
    print('Already fixed or pattern not found')
    print(f'old in content: {old in content}')
    print(f'new in content: {new in content}')
PYEOF
'''))

# 3. Проверяем результат
print('\n=== Updated User model (tax_system line) ===')
print(run('grep -n "tax_system" /opt/ai-buhgalter/backend/app/models/user.py'))

# 4. Перезапустить backend (uvicorn --reload подхватит)
print('\n=== Restart backend ===')
print(run('docker restart ai_buhgalter_backend 2>&1'))
time.sleep(8)

# 5. Backend logs
print('\n=== Backend logs ===')
print(run('docker logs --tail=15 ai_buhgalter_backend 2>&1'))

# 6. Тест регистрации
print('\n=== Test register ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"testfix10@test.com","password":"test12345678","full_name":"Test Fix10"}' '''))

# 7. Backend logs after test
print('\n=== Backend logs after test ===')
print(run('docker logs --tail=10 ai_buhgalter_backend 2>&1'))

ssh.close()
print('\nDone!')