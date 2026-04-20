import sqlite3
import sys

db_path = 'data/users.db'
if len(sys.argv) > 1:
    db_path = sys.argv[1]

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get all roles
cur.execute("SELECT DISTINCT role FROM role_permissions ORDER BY role")
roles = [r[0] for r in cur.fetchall()]
print("All roles:", roles)

# Get permissions for each role
for role in roles:
    cur.execute("SELECT permission FROM role_permissions WHERE role = ? AND permission != '' ORDER BY permission", (role,))
    perms = [r[0] for r in cur.fetchall()]
    print(f"  {role}: {len(perms)} perms - {perms}")

conn.close()
