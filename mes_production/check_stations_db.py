from utils.db_connection import DBConnection
from config import load_config

try:
    config = load_config()
    db = DBConnection(config['database'])
except Exception:
    print("Ошибка загрузки конфигурации. Используйте PostgreSQL конфигурацию в config.yaml")
    exit(1)

conn = db.get_connection()
cur = db.cursor(conn)
cur.execute('SELECT * FROM stations ORDER BY id')
rows = cur.fetchall()
print("Станции в БД:")
for row in rows:
    print(dict(row))
conn.close()