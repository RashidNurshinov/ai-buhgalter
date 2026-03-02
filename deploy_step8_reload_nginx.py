"""Шаг 8: Перезагрузить nginx и тестировать."""
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

# 1. Перезапустить nginx контейнер (чтобы он подхватил DNS docker_default)
print('=== Restart nginx ===')
print(run('docker restart ai_buhgalter_nginx 2>&1'))
time.sleep(3)

# 2. Проверить что nginx подключен к docker_default
print('\n=== Nginx networks after restart ===')
print(run('docker inspect ai_buhgalter_nginx --format "{{json .NetworkSettings.Networks}}" 2>&1'))

# Если nginx отвалился от docker_default после рестарта, переподключим
print('\n=== Reconnect nginx to docker_default if needed ===')
print(run('docker network connect docker_default ai_buhgalter_nginx 2>&1'))
print(run('docker exec ai_buhgalter_nginx nginx -s reload 2>&1'))

# 3. Тест связи nginx -> backend
print('\n=== Test nginx -> backend (from nginx container) ===')
print(run('docker exec ai_buhgalter_nginx wget -qO- http://backend:8000/docs 2>&1 | head -5'))

# 4. Тест регистрации через nginx
print('\n=== Test register ===')
result = run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"testfix8@test.com","password":"test12345678","full_name":"Test Fix8"}' ''')
print(result)

# 5. Если всё ещё 502, тест напрямую backend
print('\n=== Test backend directly (via docker exec) ===')
print(run('docker exec ai_buhgalter_backend python3 -c "import urllib.request; r=urllib.request.urlopen(\'http://localhost:8000/api/v1/auth/register\'); print(r.read().decode())" 2>&1'))

# 6. Backend logs
print('\n=== Backend logs ===')
print(run('docker logs --tail=30 ai_buhgalter_backend 2>&1'))

# 7. Nginx error logs
print('\n=== Nginx error logs ===')
print(run('docker logs --tail=20 ai_buhgalter_nginx 2>&1'))

ssh.close()
print('\nDone!')