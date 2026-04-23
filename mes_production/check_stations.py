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

print("=== Orders with current_station showing exact value ===")
cursor.execute("""
    SELECT id, order_number, current_station, 
           current_station::text as station_text,
           current_station::numeric(10,5) as station_numeric
    FROM orders 
    WHERE status = 'production'
""")
for row in cursor.fetchall():
    print(f"ID={row[0]}, {row[1]}, station={row[2]}, text='{row[3]}', numeric={row[4]}")

print("\n=== Testing different comparisons for 6.1 ===")
cursor.execute("SELECT id, order_number FROM orders WHERE current_station = 6.1 AND status = 'production'")
print(f"current_station = 6.1: {cursor.fetchall()}")

cursor.execute("SELECT id, order_number FROM orders WHERE current_station = 6.10::numeric AND status = 'production'")
print(f"current_station = 6.10::numeric: {cursor.fetchall()}")

cursor.execute("SELECT id, order_number FROM orders WHERE current_station::text = '6.1' AND status = 'production'")
print(f"current_station::text = '6.1': {cursor.fetchall()}")

cursor.execute("SELECT id, order_number FROM orders WHERE ROUND(current_station::numeric, 1) = 6.1 AND status = 'production'")
print(f"ROUND(current_station::numeric, 1) = 6.1: {cursor.fetchall()}")

cursor.close()
conn.close()