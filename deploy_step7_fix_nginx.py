"""Шаг 7: Починить nginx - он orphan и не в той сети."""
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

# 1. Check nginx config
print('=== Nginx config ===')
print(run('docker exec ai_buhgalter_nginx cat /etc/nginx/conf.d/default.conf 2>&1'))

# 2. Check what network nginx is on
print('\n=== Nginx networks ===')
print(run('docker inspect ai_buhgalter_nginx --format "{{json .NetworkSettings.Networks}}" 2>&1'))

# 3. Check what network backend is on
print('\n=== Backend networks ===')
print(run('docker inspect ai_buhgalter_backend --format "{{json .NetworkSettings.Networks}}" 2>&1'))

# 4. Check all docker networks 
print('\n=== Docker networks ===')
print(run('docker network ls'))

# 5. Connect nginx to docker_default network
print('\n=== Connect nginx to docker_default ===')
print(run('docker network connect docker_default ai_buhgalter_nginx 2>&1'))

# 6. Test directly from backend container
print('\n=== Test backend health directly ===')
print(run('docker exec ai_buhgalter_backend curl -s http://localhost:8000/api/v1/health 2>&1'))

# 7. Test from nginx container to backend
print('\n=== Test nginx -> backend ===')
print(run('docker exec ai_buhgalter_nginx curl -s http://backend:8000/api/v1/health 2>&1 || docker exec ai_buhgalter_nginx wget -qO- http://backend:8000/api/v1/health 2>&1'))

# 8. Backend logs after startup
print('\n=== Backend logs ===')
print(run('docker logs --tail=40 ai_buhgalter_backend 2>&1'))

# 9. Test register via nginx
print('\n=== Test register ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"testfix7@test.com","password":"test12345678","full_name":"Test Fix7"}' '''))

ssh.close()
print('\nDone!')