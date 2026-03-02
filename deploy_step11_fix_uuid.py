"""Шаг 11: Исправить тип колонки id - VARCHAR -> UUID."""
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

# 1. Check current table schema
print('=== users table schema ===')
print(run('''docker exec ai_buhgalter_postgres psql -h localhost -U postgres -d ai_buhgalter -c "\\d users" 2>&1'''))

# 2. Check base model
print('\n=== Base model ===')
print(run('cat /opt/ai-buhgalter/backend/app/models/base.py'))

# 3. Check auth_service to see where it queries by id
print('\n=== auth_service.py ===')
print(run('cat /opt/ai-buhgalter/backend/app/services/auth_service.py'))

# 4. The simplest fix: ALTER TABLE to change id column type  
print('\n=== Fix: ALTER users.id to UUID type ===')
fix_sql = """
-- Сначала удалим зависимости (если есть) и поменяем тип
ALTER TABLE users ALTER COLUMN id TYPE uuid USING id::uuid;
"""
print(run(f'''docker exec ai_buhgalter_postgres psql -h localhost -U postgres -d ai_buhgalter -c "{fix_sql}" 2>&1'''))

# 5. Check schema after fix
print('\n=== users table schema after fix ===')
print(run('''docker exec ai_buhgalter_postgres psql -h localhost -U postgres -d ai_buhgalter -c "\\d users" 2>&1'''))

# 6. Also check all tables - maybe more have VARCHAR id
print('\n=== All tables ===')
print(run('''docker exec ai_buhgalter_postgres psql -h localhost -U postgres -d ai_buhgalter -c "\\dt" 2>&1'''))

# 7. Test register
print('\n=== Test register ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"testfix11@test.com","password":"test12345678","full_name":"Test Fix11"}' '''))

# 8. Backend logs
print('\n=== Backend logs (last 10) ===')
print(run('docker logs --tail=10 ai_buhgalter_backend 2>&1'))

ssh.close()
print('\nDone!')