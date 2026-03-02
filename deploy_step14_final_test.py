"""Шаг 14: Финальный тест — регистрация, логин, получение профиля."""
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

time.sleep(5)
ssh = connect_ssh()
print('Connected!')

def run(cmd, timeout=30):
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    return stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')

# 1. Test register new user
print('=== 1. Register ===')
print(run('''curl -s -w "\\nHTTP:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"finaltest@test.com","password":"test12345678","full_name":"Final Test User"}' '''))

# 2. Test login
print('\n=== 2. Login ===')
login_result = run('''curl -s -X POST http://localhost/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"finaltest@test.com","password":"test12345678"}' ''')
print(login_result)

# Extract access token
import json
try:
    token_data = json.loads(login_result.strip())
    access_token = token_data.get('access_token', '')
    print(f'\nToken: {access_token[:50]}...')
except:
    access_token = ''
    print('Failed to parse token')

# 3. Test /me endpoint (if exists)
if access_token:
    print('\n=== 3. GET /me ===')
    print(run(f'''curl -s -w "\\nHTTP:%{{http_code}}" http://localhost/api/v1/auth/me -H "Authorization: Bearer {access_token}" '''))

# 4. Test frontend accessibility
print('\n=== 4. Frontend ===')
print(run('curl -s -o /dev/null -w "HTTP:%{http_code}" http://localhost/ 2>&1'))

# 5. Test API health
print('\n=== 5. API health ===')
print(run('curl -s http://localhost/api/v1/health 2>&1'))

# 6. Test duplicate registration (should fail)
print('\n=== 6. Duplicate register ===')
print(run('''curl -s -w "\\nHTTP:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"finaltest@test.com","password":"test12345678","full_name":"Duplicate"}' '''))

# 7. Test wrong password login
print('\n=== 7. Wrong password ===')
print(run('''curl -s -w "\\nHTTP:%{http_code}" -X POST http://localhost/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"finaltest@test.com","password":"wrongpassword"}' '''))

# 8. Check DB for users
print('\n=== 8. Users in DB ===')
print(run('''docker exec ai_buhgalter_postgres psql -h localhost -U postgres -d ai_buhgalter -c "SELECT id, email, full_name, tax_system, created_at FROM users" 2>&1'''))

# 9. Backend status
print('\n=== 9. Docker status ===')
print(run('docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>&1'))

ssh.close()
print('\n✅ All tests complete!')