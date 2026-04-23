import psycopg2
import yaml

with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

pg_config = config['database']
conn = psycopg2.connect(
    host=pg_config['host'],
    port=pg_config['port'],
    dbname=pg_config['name'],
    user=pg_config['user'],
    password=pg_config['password']
)
cursor = conn.cursor()

print("=== ALL ORDERS ===")
cursor.execute('SELECT id, order_number, batch, product_code, color, status, current_station, completed_subs FROM orders ORDER BY id DESC')
for row in cursor.fetchall():
    print(f"ID={row[0]}, {row[1]}, status={row[5]}, station={row[6]}, completed_subs={row[7]}")

print("\n=== ORDERS AT STATION 6 ===")
cursor.execute("SELECT id, order_number, current_station FROM orders WHERE current_station = 6.0 AND status = 'production'")
for row in cursor.fetchall():
    print(row)

print("\n=== ORDERS AT STATION 6.1 ===")
cursor.execute("SELECT id, order_number, current_station FROM orders WHERE current_station = %s AND status = 'production'", (6.1,))
for row in cursor.fetchall():
    print(row)

cursor.close()
conn.close()
