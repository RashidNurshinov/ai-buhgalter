"""Шаг 10: Исправить enum - проблема case sensitivity."""
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

time.sleep(3)
ssh = connect_ssh()
print('Connected!')

def run(cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')

# 1. Проверить .env на предмет DB credentials
print('=== .env DB settings ===')
print(run('grep -E "^(POSTGRES|DATABASE)" /opt/ai-buhgalter/.env'))

# 2. Проверить enum с правильным подключением (через docker exec и -h localhost)
print('\n=== PostgreSQL enum values (via network) ===')
print(run('''docker exec ai_buhgalter_postgres psql -h localhost -U postgres -d ai_buhgalter -c "SELECT unnest(enum_range(NULL::tax_system_enum));" 2>&1'''))

# 3. Посмотрим init.sql
print('\n=== Init SQL ===')
print(run('cat /opt/ai-buhgalter/docker/postgres/init.sql 2>&1'))

# 4. Посмотрим модель User — как определён enum
print('\n=== User model TaxSystem enum ===')
print(run('cat /opt/ai-buhgalter/backend/app/models/user.py 2>&1'))

# 5. Python TaxSystem enum values  
print('\n=== Python TaxSystem values ===')
print(run('''docker exec ai_buhgalter_backend python3 -c "
from app.models.user import TaxSystem
for v in TaxSystem:
    print(repr(v.name), repr(v.value))
" 2>&1'''))

ssh.close()
print('\nDone!')