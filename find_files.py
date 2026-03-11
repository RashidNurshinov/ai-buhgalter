"""
Проверка где реально находятся файлы
"""
import paramiko
import time
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HOST = "138.124.108.144"
USERNAME = "root"
PASSWORD = "jlGGd9v9cnhq"

def ssh_exec(client, command, timeout=30):
    for attempt in range(3):
        try:
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            output = stdout.read().decode('utf-8', errors='replace')
            err = stderr.read().decode('utf-8', errors='replace')
            return output + err
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
            else:
                return f"Error: {e}"
    return ""

def main():
    print("=" * 60)
    print("ПОИСК ФАЙЛОВ")
    print("=" * 60)
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOST, username=USERNAME, password=PASSWORD, timeout=30)
        
        # 1. Проверка /opt/ai-buhgalter/storage/uploads
        print("\n" + "=" * 60)
        print("1. /opt/ai-buhgalter/storage/uploads")
        print("=" * 60)
        ls1 = ssh_exec(client, "ls -laR /opt/ai-buhgalter/storage/uploads/ 2>&1", timeout=30)
        print(ls1[:3000] if ls1 else "Пусто или не найдено")
        
        # 2. Проверка /app/storage в контейнере
        print("\n" + "=" * 60)
        print("2. /app/storage В КОНТЕЙНЕРЕ")
        print("=" * 60)
        ls2 = ssh_exec(client, "docker exec ai_buhgalter_backend ls -laR /app/storage/ 2>&1", timeout=30)
        print(ls2[:3000] if ls2 else "Пусто или не найдено")
        
        # 3. Проверка /app/app/storage в контейнере
        print("\n" + "=" * 60)
        print("3. /app/app/storage В КОНТЕЙНЕРЕ")
        print("=" * 60)
        ls3 = ssh_exec(client, "docker exec ai_buhgalter_backend ls -laR /app/app/storage/ 2>&1", timeout=30)
        print(ls3[:3000] if ls3 else "Пусто или не найдено")
        
        # 4. Проверка config.py - где upload_path
        print("\n" + "=" * 60)
        print("4. UPLOAD_PATH В CONFIG")
        print("=" * 60)
        config = ssh_exec(client, "docker exec ai_buhgalter_backend grep -n 'upload_path\\|UPLOAD' /app/app/core/config.py 2>&1", timeout=30)
        print(config)
        
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
