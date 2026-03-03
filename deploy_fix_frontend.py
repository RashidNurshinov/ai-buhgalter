"""Deploy fixed frontend files to server and rebuild nginx container."""
import paramiko
import os

HOST = "31.129.110.93"
USER = "root"
KEY_PATH = os.path.join(os.path.expanduser("~"), ".ssh", "id_ed25519")

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    print(f"Connecting to {HOST} with key {KEY_PATH}...")
    ssh.connect(HOST, username=USER, key_filename=KEY_PATH, timeout=30)
    print("Connected!")
    
    sftp = ssh.open_sftp()
    
    # Upload fixed frontend source files
    files_to_upload = [
        ("frontend/src/pages/UploadPage.tsx", "/root/nalog/frontend/src/pages/UploadPage.tsx"),
        ("frontend/src/pages/DashboardPage.tsx", "/root/nalog/frontend/src/pages/DashboardPage.tsx"),
        ("frontend/src/pages/OperationsPage.tsx", "/root/nalog/frontend/src/pages/OperationsPage.tsx"),
        ("frontend/src/pages/CalendarPage.tsx", "/root/nalog/frontend/src/pages/CalendarPage.tsx"),
    ]
    
    for local_path, remote_path in files_to_upload:
        full_local = os.path.join(r"c:\projects\nalog", local_path)
        print(f"  Uploading {local_path}")
        sftp.put(full_local, remote_path)
    
    # Upload the pre-built dist directory
    dist_dir = r"c:\projects\nalog\frontend\dist"
    remote_dist = "/root/nalog/frontend/dist"
    
    def ensure_remote_dir(path):
        try:
            sftp.stat(path)
        except FileNotFoundError:
            sftp.mkdir(path)
    
    def upload_dir(local_dir, remote_dir):
        ensure_remote_dir(remote_dir)
        for item in os.listdir(local_dir):
            local_item = os.path.join(local_dir, item)
            remote_item = f"{remote_dir}/{item}"
            if os.path.isdir(local_item):
                upload_dir(local_item, remote_item)
            else:
                sftp.put(local_item, remote_item)
    
    print("  Uploading built dist/...")
    upload_dir(dist_dir, remote_dist)
    print("  Dist uploaded.")
    
    sftp.close()
    
    # Rebuild nginx container (which serves the frontend dist)
    commands = [
        "cd /root/nalog && docker compose -f docker/docker-compose.yml up -d --build nginx",
    ]
    
    for cmd in commands:
        print(f"\n>>> {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out:
            print(out)
        if err:
            print(err)
        print(f"Exit code: {exit_code}")
    
    # Check status
    print("\n=== Container Status ===")
    stdin, stdout, stderr = ssh.exec_command("cd /root/nalog && docker compose -f docker/docker-compose.yml ps")
    print(stdout.read().decode())
    
    ssh.close()
    print("Done!")

if __name__ == "__main__":
    main()