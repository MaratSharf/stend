import yaml
import psycopg2

# Load config
with open('config.yaml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

# PostgreSQL connection
pg_config = config['database']
conn = psycopg2.connect(
    host=pg_config['host'],
    port=pg_config['port'],
    dbname=pg_config['name'],
    user=pg_config['user'],
    password=pg_config['password']
)
cursor = conn.cursor()

# Flatten stations from config
def flatten_stations(station_names):
    result = []
    main_idx = 0
    for entry in station_names:
        main_idx += 1
        if isinstance(entry, dict):
            name = entry.get('name', '')
            subs = entry.get('subs', [])
            for si, sname in enumerate(subs, 1):
                result.append((float(f"{main_idx}.{si}"), sname))
            result.append((float(main_idx), name))
        else:
            result.append((float(main_idx), entry))
    return result

station_config = config['stations']
flat = flatten_stations(station_config)

print("Expected stations:")
for sid, name in flat:
    print(f"  {sid} - {name}")

# Check existing stations
cursor.execute('SELECT id, name FROM stations ORDER BY id')
existing = cursor.fetchall()
print("\nExisting stations in DB:")
for sid, name in existing:
    print(f"  {sid} - {name}")

# Find missing stations
existing_ids = {row[0] for row in existing}
missing = [(sid, name) for sid, name in flat if sid not in existing_ids]

if missing:
    print(f"\nAdding {len(missing)} missing station(s):")
    for sid, name in missing:
        cursor.execute('INSERT INTO stations (id, name, order_id) VALUES (%s, %s, NULL)', (sid, name))
        print(f"  Added: {sid} - {name}")
    conn.commit()
else:
    print("\nAll stations exist. No changes needed.")

# Check for extra stations
extra = [(sid, name) for sid, name in existing if sid not in {s[0] for s in flat}]
if extra:
    print(f"\nWarning: {len(extra)} extra station(s) in DB:")
    for sid, name in extra:
        print(f"  {sid} - {name}")

cursor.close()
conn.close()

print("\nDone!")
