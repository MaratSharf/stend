"""
Script to migrate role_permissions in users.db with new screen-based permissions - PostgreSQL version.
Run this once after updating permissions.py to reset built-in roles.
"""
import sys
import os
from utils.db_connection import DBConnection
from utils.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSIONS


def migrate_user_db(db_path: str = 'data/users.db') -> None:
    """Update role_permissions table with new permission keys."""
    print(f"Connecting to {db_path}...")
    
    if not db_path:
        print("Error: Database path not provided")
        sys.exit(1)
    
    # Use config if available, otherwise direct path
    try:
        from config import load_config
        config = load_config()
        db = DBConnection(config['database'])
    except:
        db = DBConnection(db_path)
    
    conn = db.get_connection()
    try:
        cursor = db.cursor(conn)
        ph = db.placeholder()
        
        # Check if tables exist (PostgreSQL version)
        cursor.execute("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'role_permissions')")
        if not cursor.fetchone()['exists']:
            print("Table 'role_permissions' not found. Skipping migration.")
            return
        
        # Get all existing roles
        cursor.execute("SELECT DISTINCT role FROM role_permissions ORDER BY role")
        existing_roles = [row['role'] for row in cursor.fetchall()]
        print(f"Found roles: {existing_roles}")
        
        # Reset built-in roles to new defaults
        built_in_roles = ['admin', 'operator', 'viewer']
        
        for role in built_in_roles:
            if role in existing_roles:
                print(f"\nResetting role '{role}' to new defaults...")
                
                # Delete existing permissions
                cursor.execute(f"DELETE FROM role_permissions WHERE role = {ph}", (role,))
                
                # Get new defaults
                new_perms = DEFAULT_ROLE_PERMISSIONS.get(role, [])
                print(f"  New permissions: {new_perms}")
                
                # Insert new permissions
                for perm in new_perms:
                    if perm in PERMISSIONS:
                        cursor.execute(
                            f"INSERT INTO role_permissions (role, permission) VALUES ({ph}, {ph})",
                            (role, perm)
                        )
                    else:
                        print(f"  Warning: Permission '{perm}' not found in PERMISSIONS dict")
                
                conn.commit()
                print(f"  Done: {len(new_perms)} permission(s) assigned")
            else:
                print(f"\nRole '{role}' not found in database. Skipping.")
        
        # Verify results
        print("\n" + "="*50)
        print("Verification:")
        for role in built_in_roles:
            cursor.execute(
                f"SELECT permission FROM role_permissions WHERE role = {ph} AND permission != '' ORDER BY permission",
                (role,)
            )
            perms = [row['permission'] for row in cursor.fetchall()]
            print(f"  {role}: {len(perms)} permission(s) - {perms[:5]}{'...' if len(perms) > 5 else ''}")
        
        print("\nMigration completed successfully!")
        
    except Exception as e:
        print(f"Database error: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    # Default path relative to project root
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'users.db')
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    migrate_user_db(db_path)