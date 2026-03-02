"""Шаг 13: Исправить миграцию — sa.String(36) -> postgresql.UUID, затем пересоздать."""
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
            time.sleep(10)
    raise Exception('Failed to connect')

time.sleep(8)
ssh = connect_ssh()
print('Connected!')

def run(cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')

# 1. Fix migration file directly using sed (replace sa.String(36) with postgresql.UUID(as_uuid=True))
print('=== Fix migration with sed ===')

# Replace all sa.String(36) with postgresql.UUID(as_uuid=True) in migration
print(run(r'''
cd /opt/ai-buhgalter/backend
# First backup
cp alembic/versions/001_initial_schema.py alembic/versions/001_initial_schema.py.bak

# Replace sa.String(36) with postgresql.UUID(as_uuid=True) for id and FK columns
sed -i 's/sa\.String(36)/postgresql.UUID(as_uuid=True)/g' alembic/versions/001_initial_schema.py

echo "Sed done"
'''))

# 2. Verify changes
print('\n=== Verify: grep for UUID in migration ===')
print(run('grep -n "UUID\\|String(36)" /opt/ai-buhgalter/backend/alembic/versions/001_initial_schema.py | head -20'))

# 3. Drop all tables and alembic version
print('\n=== Drop all tables ===')
drop_sql = """
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;
"""
print(run(f'''docker exec ai_buhgalter_postgres psql -h localhost -U postgres -d ai_buhgalter -c "{drop_sql}" 2>&1'''))

# 4. Run alembic upgrade
print('\n=== Run alembic upgrade ===')
# Restart backend first to clear cached connections
print(run('docker restart ai_buhgalter_backend 2>&1'))
time.sleep(8)
print(run('docker exec ai_buhgalter_backend alembic upgrade head 2>&1', timeout=30))

# 5. Verify schema
print('\n=== Users table schema ===')
print(run('''docker exec ai_buhgalter_postgres psql -h localhost -U postgres -d ai_buhgalter -c "\\d users" 2>&1'''))

# 6. Test register  
print('\n=== Test register ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"testfix13@test.com","password":"test12345678","full_name":"Test Fix13"}' '''))

# 7. Backend logs
print('\n=== Backend logs (last 10) ===')
print(run('docker logs --tail=10 ai_buhgalter_backend 2>&1'))

ssh.close()
print('\nDone!')