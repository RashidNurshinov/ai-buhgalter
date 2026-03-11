# -*- coding: utf-8 -*-
"""
Step 6: Fix the model-DB mismatch.
DB column = 'deadline', model field = 'due_date' -> change model to 'deadline'
Also revert the wrong sed replacements from step 5
"""
import paramiko
import sys
import time

HOST = "138.124.108.144"
USER = "root"
PASSWORD = "jlGGd9v9cnhq"
PROJECT_PATH = "/opt/ai-buhgalter"

def run_cmd(ssh, cmd, desc=""):
    if desc:
        print(f"\n--- {desc} ---")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    out_safe = out.encode('ascii', errors='replace').decode('ascii')
    err_safe = err.encode('ascii', errors='replace').decode('ascii')
    if out_safe.strip():
        print(out_safe[:3000])
    if err_safe.strip():
        print(f"[STDERR] {err_safe[:2000]}")
    return out, err

def main():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(HOST, username=USER, password=PASSWORD, timeout=10)
        print("[OK] Connected!")

        # === FIX 1: Model - change due_date back to deadline ===
        print("\n" + "="*60)
        print("  FIX: Model TaxCalendarEvent - due_date -> deadline")
        print("="*60)
        
        run_cmd(ssh,
            f"sed -i 's/due_date: Mapped\\[date\\]/deadline: Mapped[date]/' {PROJECT_PATH}/backend/app/models/tax_calendar_event.py",
            "Model: due_date -> deadline field name")

        # === FIX 2: Revert tax_calendar_service.py - put deadline back ===
        run_cmd(ssh,
            f"sed -i 's/TaxCalendarEvent\\.due_date/TaxCalendarEvent.deadline/g' {PROJECT_PATH}/backend/app/services/tax_calendar_service.py",
            "Revert: TaxCalendarEvent.due_date -> TaxCalendarEvent.deadline in service")
        
        run_cmd(ssh,
            f"sed -i 's/due_date=tmpl\\.due_date/deadline=tmpl.deadline/g' {PROJECT_PATH}/backend/app/services/tax_calendar_service.py",
            "Revert: due_date=tmpl.due_date -> deadline=tmpl.deadline")

        run_cmd(ssh,
            f"sed -i 's/AND due_date < :today/AND deadline < :today/g' {PROJECT_PATH}/backend/app/services/tax_calendar_service.py",
            "Revert: raw SQL due_date -> deadline")

        # === FIX 3: agent_tools.py - e.due_date -> e.deadline ===
        run_cmd(ssh,
            f"sed -i 's/str(e\\.due_date)/str(e.deadline)/g' {PROJECT_PATH}/backend/app/services/agent_tools.py",
            "Revert: str(e.due_date) -> str(e.deadline) in agent_tools")
        
        run_cmd(ssh,
            f"sed -i 's/e\\.due_date/e.deadline/g' {PROJECT_PATH}/backend/app/services/agent_tools.py",
            "Revert: e.due_date -> e.deadline in agent_tools")

        # === FIX 4: dashboard_service.py - revert ===
        run_cmd(ssh,
            f"sed -i 's/TaxCalendarEvent\\.due_date/TaxCalendarEvent.deadline/g' {PROJECT_PATH}/backend/app/services/dashboard_service.py 2>/dev/null",
            "Revert: dashboard_service.py due_date -> deadline")

        # === FIX 5: Schema - revert due_date -> deadline ===
        run_cmd(ssh,
            f"sed -i 's/due_date: date/deadline: date/g' {PROJECT_PATH}/backend/app/schemas/tax_calendar.py 2>/dev/null",
            "Revert: schema due_date -> deadline")

        # === FIX 6: calendar API - revert ===
        run_cmd(ssh,
            f"sed -i 's/TaxCalendarEvent\\.due_date/TaxCalendarEvent.deadline/g' {PROJECT_PATH}/backend/app/api/v1/calendar.py 2>/dev/null",
            "Revert: calendar API due_date -> deadline")

        # === VERIFY ===
        run_cmd(ssh,
            f"grep -n 'due_date' {PROJECT_PATH}/backend/app/models/tax_calendar_event.py",
            "VERIFY model: should NOT have due_date")

        run_cmd(ssh,
            f"grep -n 'deadline' {PROJECT_PATH}/backend/app/models/tax_calendar_event.py",
            "VERIFY model: should have deadline")

        run_cmd(ssh,
            f"grep -rn 'due_date' {PROJECT_PATH}/backend/app/services/tax_calendar_service.py || echo 'CLEAN - no due_date'",
            "VERIFY service: should NOT have due_date")

        run_cmd(ssh,
            f"grep -rn 'due_date' {PROJECT_PATH}/backend/app/services/agent_tools.py || echo 'CLEAN - no due_date'",
            "VERIFY agent_tools: should NOT have due_date")

        # === Trigger reload ===
        run_cmd(ssh,
            f"touch {PROJECT_PATH}/backend/app/main.py",
            "Trigger uvicorn reload")

        print("  Waiting 5 seconds...")
        time.sleep(5)

        run_cmd(ssh,
            "docker logs --tail=5 ai_buhgalter_backend 2>&1",
            "Backend logs")

        run_cmd(ssh,
            "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80/api/docs",
            "API docs status")

        print("\n[DONE] Model-DB sync complete. Everything uses 'deadline'.")

    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    finally:
        ssh.close()

if __name__ == "__main__":
    main()