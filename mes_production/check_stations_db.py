from utils.db_connection import DBConnection

db = DBConnection('data/mes.db')
conn = db.get_connection()
cur = db.cursor(conn)
cur.execute('SELECT * FROM stations ORDER BY id')
rows = cur.fetchall()
print("Станции в БД:")
for row in rows:
    print(dict(row))
conn.close()
