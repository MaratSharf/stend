"""
Script to delete test roles from users.db
"""
import sqlite3
import sys
import os


def delete_test_roles(db_path: str = 'data/users.db') -> None:
    """Delete test roles from role_permissions table."""
    print(f"Connecting to {db_path}...")
    
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        # Get all roles
        cursor.execute("SELECT DISTINCT role FROM role_permissions ORDER BY role")
        all_roles = [row[0] for row in cursor.fetchall()]
        print(f"Current roles: {all_roles}")
        
        # Built-in roles to keep
        built_in_roles = {'admin', 'operator', 'viewer'}
        
        # Find test roles
        test_roles = [r for r in all_roles if r not in built_in_roles]
        
        if not test_roles:
            print("No test roles found. Nothing to delete.")
            return
        
        print(f"\nTest roles to delete: {test_roles}")
        
        # Confirm deletion
        confirm = input("Delete these roles? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Cancelled.")
            return
        
        # Delete test roles
        for role in test_roles:
            cursor.execute("DELETE FROM role_permissions WHERE role = ?", (role,))
            print(f"  Deleted role: {role}")
        
        conn.commit()
        
        # Verify
        cursor.execute("SELECT DISTINCT role FROM role_permissions ORDER BY role")
        remaining = [row[0] for row in cursor.fetchall()]
        print(f"\nRemaining roles: {remaining}")
        print("Done!")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == '__main__':
    db_path = os.path.join(os.path.dirname(__file__), 'data', 'users.db')
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    
    delete_test_roles(db_path)