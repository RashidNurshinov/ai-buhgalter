import os
# -*- coding: utf-8 -*-
"""
Step 5: Fix TaxCalendarEvent.deadline -> due_date everywhere
Also check actual DB column name
"""
import paramiko
import sys
import time

HOST = os.environ.get("DEPLOY_HOST", "")
USER = "root"
PASSWORD = os.environ.get("DEPLOY_SSH_PASSWORD", "")
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

        # Check actual DB column
        run_cmd(ssh,
            "docker exec ai_buhgalter_postgres psql -U postgres -d ai_buhgalter -c '\\d tax_calendar_events' 2>&1",
            "DB: tax_calendar_events columns")

        # Check all files that reference TaxCalendarEvent.deadline
        run_cmd(ssh,
            f"grep -rn 'deadline' {PROJECT_PATH}/backend/app/services/tax_calendar_service.py",
            "tax_calendar_service.py - deadline references")

        run_cmd(ssh,
            f"grep -rn 'deadline' {PROJECT_PATH}/backend/app/services/dashboard_service.py 2>/dev/null",
            "dashboard_service.py - deadline references")

        run_cmd(ssh,
            f"grep -rn 'deadline' {PROJECT_PATH}/backend/app/schemas/tax_calendar.py 2>/dev/null",
            "schemas/tax_calendar.py - deadline references")

        # Fix tax_calendar_service.py: TaxCalendarEvent.deadline -> TaxCalendarEvent.due_date
        run_cmd(ssh,
            f"sed -i 's/TaxCalendarEvent\\.deadline/TaxCalendarEvent.due_date/g' {PROJECT_PATH}/backend/app/services/tax_calendar_service.py",
            "FIX: TaxCalendarEvent.deadline -> TaxCalendarEvent.due_date in tax_calendar_service")
        
        # Fix deadline= in object creation -> due_date=
        run_cmd(ssh,
            f"sed -i 's/deadline=tmpl\\.deadline/due_date=tmpl.due_date/g' {PROJECT_PATH}/backend/app/services/tax_calendar_service.py",
            "FIX: deadline=tmpl.deadline -> due_date=tmpl.due_date")

        # Fix raw SQL: deadline -> due_date
        run_cmd(ssh,
            f"sed -i 's/AND deadline < :today/AND due_date < :today/g' {PROJECT_PATH}/backend/app/services/tax_calendar_service.py",
            "FIX: raw SQL deadline -> due_date")

        # Fix agent_tools.py - remaining e.deadline in tool_get_upcoming_deadlines
        run_cmd(ssh,
            f"sed -i 's/str(e\\.deadline)/str(e.due_date)/g' {PROJECT_PATH}/backend/app/services/agent_tools.py",
            "FIX: str(e.deadline) -> str(e.due_date) in agent_tools")

        # Fix dashboard_service.py if it has deadline references
        run_cmd(ssh,
            f"sed -i 's/TaxCalendarEvent\\.deadline/TaxCalendarEvent.due_date/g' {PROJECT_PATH}/backend/app/services/dashboard_service.py 2>/dev/null",
            "FIX: dashboard_service.py deadline -> due_date")

        # Fix schemas
        run_cmd(ssh,
            f"grep -rn 'deadline' {PROJECT_PATH}/backend/app/schemas/ 2>/dev/null",
            "Check schemas for deadline")

        # Fix tax_calendar.py schema if needed
        run_cmd(ssh,
            f"sed -i 's/deadline: date/due_date: date/g' {PROJECT_PATH}/backend/app/schemas/tax_calendar.py 2>/dev/null",
            "FIX: schema deadline -> due_date (if any)")

        # Fix calendar API endpoint
        run_cmd(ssh,
            f"grep -rn 'deadline' {PROJECT_PATH}/backend/app/api/v1/calendar.py 2>/dev/null",
            "Check calendar API for deadline")

        run_cmd(ssh,
            f"sed -i 's/TaxCalendarEvent\\.deadline/TaxCalendarEvent.due_date/g' {PROJECT_PATH}/backend/app/api/v1/calendar.py 2>/dev/null",
            "FIX: calendar API deadline -> due_date")

        # Also check tax_calendar constants
        run_cmd(ssh,
            f"grep -rn 'deadline' {PROJECT_PATH}/backend/app/constants/tax_calendar.py 2>/dev/null",
            "Check tax_calendar constants for deadline field")

        # Verify no more TaxCalendarEvent.deadline references
        run_cmd(ssh,
            f"grep -rn 'TaxCalendarEvent\\.deadline' {PROJECT_PATH}/backend/app/ 2>/dev/null || echo 'NO MORE REFERENCES - CLEAN!'",
            "VERIFY: No more TaxCalendarEvent.deadline references")

        # Touch to trigger reload
        run_cmd(ssh,
            f"touch {PROJECT_PATH}/backend/app/main.py",
            "Trigger uvicorn reload")

        print("  Waiting 5 seconds for reload...")
        time.sleep(5)

        # Check backend is alive
        run_cmd(ssh,
            "docker logs --tail=5 ai_buhgalter_backend 2>&1",
            "Backend logs after fix")

        # Test an endpoint
        run_cmd(ssh,
            "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:80/api/docs",
            "API docs status")

        print("\n[DONE] Deadline field fix complete.")

    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    finally:
        ssh.close()

if __name__ == "__main__":
    main()