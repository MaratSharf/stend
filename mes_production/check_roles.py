"""
Check roles script - PostgreSQL version.
"""
import sys
from utils.db_connection import DBConnection
from config import load_config

db_path = 'data/users.db'
if len(sys.argv) > 1:
    db_path = sys.argv[1]

# Use config if available, otherwise direct path
try:
    config = load_config()
    db = DBConnection(config['database'])
except:
    db = DBConnection(db_path)

conn = db.get_connection()
try:
    cursor = db.cursor(conn)
    ph = db.placeholder()

    # Get all roles
    cursor.execute("SELECT DISTINCT role FROM role_permissions ORDER BY role")
    roles = [r['role'] for r in cursor.fetchall()]
    print("All roles:", roles)

    # Get permissions for each role
    for role in roles:
        cursor.execute("SELECT permission FROM role_permissions WHERE role = %s AND permission != '' ORDER BY permission", (role,))
        perms = [r['permission'] for r in cursor.fetchall()]
        print(f"  {role}: {len(perms)} perms - {perms}")
finally:
    conn.close()