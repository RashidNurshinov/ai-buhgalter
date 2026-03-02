"""Шаг 9: Исправить enum tax_system в PostgreSQL."""
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
            ssh.connect(
                '138.124.108.144',
                username='root',
                password='jlGGd9v9cnhq',
                timeout=60,
                banner_timeout=120,
                auth_timeout=60,
                sock=sock,
            )
            return ssh
        except Exception as e:
            print(f'Attempt {attempt+1} failed: {e}')
            time.sleep(5)
    raise Exception('Failed to connect after retries')

time.sleep(3)
ssh = connect_ssh()
print('Connected!')

def run(cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')

# 1. Проверить текущие значения enum в БД
print('=== Current enum values in PostgreSQL ===')
print(run('''docker exec ai_buhgalter_postgres psql -U ai_user -d ai_buhgalter -c "SELECT unnest(enum_range(NULL::tax_system_enum));" 2>&1'''))

# 2. Проверить что модель Python ожидает
print('\n=== Python TaxSystem enum values ===')
print(run('''docker exec ai_buhgalter_backend python3 -c "
from app.models.user import TaxSystem
for v in TaxSystem:
    print(v.name, '=', v.value)
" 2>&1'''))

# 3. Попробуем просто пересоздать enum или добавить значения
# Используем подход: DROP old enum, CREATE new с правильными значениями
print('\n=== Fix enum: drop and recreate ===')
fix_sql = """
-- Сначала посмотрим что есть
SELECT unnest(enum_range(NULL::tax_system_enum));
"""
print(run(f'''docker exec ai_buhgalter_postgres psql -U ai_user -d ai_buhgalter -c "{fix_sql}" 2>&1'''))

# Добавляем нужные значения по одному (ALTER TYPE ADD VALUE нельзя в транзакции)
for val in ['USN_INCOME', 'USN_INCOME_EXPENSE', 'PATENT', 'OSNO', 'ESHN', 'NPD', 'AUTS']:
    result = run(f'''docker exec ai_buhgalter_postgres psql -U ai_user -d ai_buhgalter -c "ALTER TYPE tax_system_enum ADD VALUE IF NOT EXISTS '{val}';" 2>&1''')
    print(f'  ADD {val}: {result.strip()}')

# 4. Проверить enum после
print('\n=== Enum values after fix ===')
print(run('''docker exec ai_buhgalter_postgres psql -U ai_user -d ai_buhgalter -c "SELECT unnest(enum_range(NULL::tax_system_enum));" 2>&1'''))

# 5. Запустить alembic миграции
print('\n=== Run alembic upgrade ===')
print(run('docker exec ai_buhgalter_backend alembic upgrade head 2>&1', timeout=30))

# 6. Тест регистрации
print('\n=== Test register ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"testfix9@test.com","password":"test12345678","full_name":"Test Fix9"}' '''))

# 7. Backend logs
print('\n=== Backend logs (last 15) ===')
print(run('docker logs --tail=15 ai_buhgalter_backend 2>&1'))

ssh.close()
print('\nDone!')