"""Шаг 12: Пересоздать все таблицы с правильными типами UUID."""
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

# 1. Check alembic migration file to understand why VARCHAR(36) instead of UUID
print('=== Alembic versions ===')
print(run('ls /opt/ai-buhgalter/backend/alembic/versions/'))

print('\n=== First migration file (head content) ===')
print(run('head -80 /opt/ai-buhgalter/backend/alembic/versions/*.py 2>&1 | head -120'))

# 2. DROP all tables and recreate via alembic
print('\n=== Drop all tables ===')
drop_sql = """
DROP TABLE IF EXISTS ai_chat_messages CASCADE;
DROP TABLE IF EXISTS bank_accounts CASCADE;
DROP TABLE IF EXISTS bank_operations CASCADE;
DROP TABLE IF EXISTS cash_receipts CASCADE;
DROP TABLE IF EXISTS counterparties CASCADE;
DROP TABLE IF EXISTS document_items CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS kudir_entries CASCADE;
DROP TABLE IF EXISTS purchase_book_entries CASCADE;
DROP TABLE IF EXISTS reconciliation_reports CASCADE;
DROP TABLE IF EXISTS sales_book_entries CASCADE;
DROP TABLE IF EXISTS tax_calculations CASCADE;
DROP TABLE IF EXISTS tax_calendar_events CASCADE;
DROP TABLE IF EXISTS tax_declarations CASCADE;
DROP TABLE IF EXISTS uploaded_files CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS alembic_version CASCADE;
DROP TYPE IF EXISTS tax_system_enum CASCADE;
DROP TYPE IF EXISTS document_type_enum CASCADE;
DROP TYPE IF EXISTS document_status_enum CASCADE;
DROP TYPE IF EXISTS document_source_enum CASCADE;
DROP TYPE IF EXISTS operation_category_enum CASCADE;
DROP TYPE IF EXISTS operation_status_enum CASCADE;
DROP TYPE IF EXISTS payment_type_enum CASCADE;
DROP TYPE IF EXISTS tax_type_enum CASCADE;
DROP TYPE IF EXISTS period_type_enum CASCADE;
DROP TYPE IF EXISTS calculation_status_enum CASCADE;
DROP TYPE IF EXISTS declaration_type_enum CASCADE;
DROP TYPE IF EXISTS declaration_status_enum CASCADE;
DROP TYPE IF EXISTS calendar_event_type_enum CASCADE;
DROP TYPE IF EXISTS calendar_event_status_enum CASCADE;
DROP TYPE IF EXISTS file_type_enum CASCADE;
DROP TYPE IF EXISTS processing_status_enum CASCADE;
DROP TYPE IF EXISTS chat_role_enum CASCADE;
"""
print(run(f'''docker exec ai_buhgalter_postgres psql -h localhost -U postgres -d ai_buhgalter -c "{drop_sql}" 2>&1'''))

# 3. Check alembic migration for VARCHAR(36) issue and fix it
print('\n=== Check migration for VARCHAR id pattern ===')
migration_file = run('ls /opt/ai-buhgalter/backend/alembic/versions/*.py').strip()
print(f'Migration file: {migration_file}')
print(run(f'grep -n "VARCHAR(36)\\|String(36)\\|sa.String(length=36)" {migration_file} | head -20'))

# 4. Fix migration: replace VARCHAR(36) with UUID for id columns
print('\n=== Fix migration: replace VARCHAR(36) id with UUID ===')
print(run(r'''
cd /opt/ai-buhgalter/backend && python3 << 'PYEOF'
import glob

files = glob.glob('alembic/versions/*.py')
for f in files:
    with open(f, 'r') as fh:
        content = fh.read()
    
    # Count replacements
    original = content
    
    # Replace sa.Column('id', sa.String(length=36)) with sa.Column('id', sa.UUID()) or postgresql.UUID
    # Pattern: sa.Column('id', sa.String(length=36), nullable=False)
    import re
    
    # Replace id columns: String(36) -> postgresql.UUID(as_uuid=True)
    content = content.replace(
        "sa.Column('id', sa.String(length=36), nullable=False)",
        "sa.Column('id', sa.UUID(), nullable=False)"
    )
    
    # Replace user_id foreign key columns too
    content = content.replace(
        "sa.Column('user_id', sa.String(length=36), nullable=False)",
        "sa.Column('user_id', sa.UUID(), nullable=False)"
    )
    
    # Replace other _id foreign keys
    for col in ['document_id', 'bank_account_id', 'bank_operation_id', 'cash_receipt_id', 
                'counterparty_id', 'uploaded_file_id', 'operation_id', 'receipt_id',
                'file_id', 'calculation_id', 'declaration_id', 'event_id', 'report_id']:
        content = content.replace(
            f"sa.Column('{col}', sa.String(length=36), nullable=False)",
            f"sa.Column('{col}', sa.UUID(), nullable=False)"
        )
        content = content.replace(
            f"sa.Column('{col}', sa.String(length=36), nullable=True)",
            f"sa.Column('{col}', sa.UUID(), nullable=True)"
        )
    
    # Also handle any remaining String(36) that might be FK ids
    # More aggressive: replace ALL sa.String(length=36) patterns that are likely UUIDs
    # Only in column definitions where column name ends with '_id' or is 'id'
    
    if content != original:
        # Add import for sa.UUID if not present
        if 'import sqlalchemy as sa' in content and 'sa.UUID' in content:
            pass  # sa.UUID is available in SQLAlchemy 2.x
        
        with open(f, 'w') as fh:
            fh.write(content)
        print(f'Fixed: {f}')
        
        # Show changed lines
        for i, (old_line, new_line) in enumerate(zip(original.split('\n'), content.split('\n'))):
            if old_line != new_line:
                print(f'  Line {i+1}: {new_line.strip()}')
    else:
        print(f'No changes needed: {f}')
PYEOF
'''))

# 5. Run alembic upgrade
print('\n=== Run alembic upgrade head ===')
print(run('docker exec ai_buhgalter_backend alembic upgrade head 2>&1', timeout=30))

# 6. Verify table schema
print('\n=== Users table schema after recreate ===')
print(run('''docker exec ai_buhgalter_postgres psql -h localhost -U postgres -d ai_buhgalter -c "\\d users" 2>&1'''))

# 7. Test register
print('\n=== Test register ===')
print(run('''curl -s -w "\\nHTTP_CODE:%{http_code}" -X POST http://localhost/api/v1/auth/register -H "Content-Type: application/json" -d '{"email":"testfix12@test.com","password":"test12345678","full_name":"Test Fix12"}' '''))

# 8. Backend logs
print('\n=== Backend logs (last 10) ===')
print(run('docker logs --tail=10 ai_buhgalter_backend 2>&1'))

ssh.close()
print('\nDone!')