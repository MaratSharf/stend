# Логика создания, запуска и перемещения заказов

## Архитектура станций

### Структура

Система состоит из **основных станций** и **подстанций**:

```
1. Приёмка                  (основная, id = 1.0)
   ├── Приёмка 1.1          (подстанция, id = 1.1)
   └── Приёмка 1.2          (подстанция, id = 1.2)
2. Сортировка               (основная, id = 2.0)
3. Подготовка               (основная, id = 3.0)
   └── Подготовка 3.1       (подстанция, id = 3.1)
4. Сборка                   (основная, id = 4.0)
5. Пайка                    (основная, id = 5.0)
6. Контроль                 (основная, id = 6.0)
7. Тестирование             (основная, id = 7.0)
8. Упаковка                 (основная, id = 8.0)
9. Маркировка               (основная, id = 9.0)
10. Отгрузка                (основная, id = 10.0)
```

### Конфигурация

Подстанции задаются в `config.yaml`:

```yaml
stations:
  - name: Приёмка
    subs:
      - Приёмка 1.1
      - Приёмка 1.2
  - name: Сортировка
  - name: Подготовка
    subs:
      - Подготовка 3.1
  # ...
```

При инициализации создаётся **плоский список** с `REAL` ID:
- Основные станции: `1.0, 2.0, 3.0, ...` (целые числа)
- Подстанции: `1.1, 1.2, 3.1, ...` (десятичные)

---

## 1. Создание заказа

### Endpoint
```
POST /api/orders
```

### Входные данные
```json
{
  "batch": "BATCH-A",
  "product_code": "MODEL-X",
  "color": "Red",
  "quantity": 3
}
```

### Логика

```
┌─────────────────────────────────────────────────┐
│  1. Генерация уникального номера заказа          │
│     INSERT → lastrowid → "ORD-{id:04d}"          │
│     UPDATE order_number WHERE id = lastrowid     │
│                                                  │
│     ✅ lastrowid атомарен — гонок нет            │
│     ✅ Каждый заказ: quantity = 1, status = "buffer" │
│     ✅ completed_subs = '' (пусто)               │
│                                                  │
│  2. Повтор для каждого из quantity               │
│                                                  │
│  3. Ответ: { success, orders[], count, message } │
└─────────────────────────────────────────────────┘
```

### Результат
```json
{
  "success": true,
  "orders": [
    { "id": 1, "order_number": "ORD-0001", "status": "buffer", "current_station": null, "completed_subs": "" },
    { "id": 2, "order_number": "ORD-0002", "status": "buffer", "current_station": null, "completed_subs": "" },
    { "id": 3, "order_number": "ORD-0003", "status": "buffer", "current_station": null, "completed_subs": "" }
  ],
  "count": 3
}
```

---

## 2. Запуск заказа в производство

### Endpoint
```
POST /api/orders/<id>/launch
```

### Условия
| Условие | Результат |
|---------|-----------|
| Заказ в статусе `buffer` | ✅ Запускается на первую станцию |
| Заказ уже в `production` | ❌ Отказ |
| Заказ завершён/отменён | ❌ Отказ |

### Логика

```
┌─────────────────────────────────────────────────┐
│  1. Проверка: status = 'buffer'                  │
│     Если нет → return False                      │
│                                                  │
│  2. UPDATE orders                                │
│     SET status = 'production'                    │
│         current_station = first_station_id (1.0) │
│         started_at = NOW                         │
│         completed_subs = ''                      │
│     WHERE id = ? AND status = 'buffer'           │
│                                                  │
│  3. INSERT station_log                           │
│     (order_id, station_id=1.0, entered_at=NOW)   │
│                                                  │
│  4. COMMIT                                       │
│                                                  │
│  5. Логирование:                                 │
│     "Order {id} launched to station 1.0"         │
└─────────────────────────────────────────────────┘
```

### Состояние после запуска
```
order #1:
  status = "production"
  current_station = 1.0        ← Приёмка (основная)
  completed_subs = ""          ← Подстанции ещё не завершены
```

---

## 3. Завершение подстанций

### Endpoint
```
POST /api/orders/<id>/complete-sub
Body: { "sub_station_id": 1.1 }
```

### Условия
| Условие | Результат |
|---------|-----------|
| Заказ в `production` | ✅ Продолжить проверку |
| Заказ НЕ в `production` | ❌ "Order not in production" |
| Заказ на родительской станции | ✅ Продолжить |
| Заказ на другой станции | ❌ "Order is not at the parent station" |
| Подстанция уже завершена | ❌ "Sub-station already completed" |

### Логика

```
┌─────────────────────────────────────────────────┐
│  1. Проверка: order.status = 'production'        │
│  2. Проверка: order.current_station = parent_id  │
│     (parent(1.1) = 1.0)                          │
│                                                  │
│  3. Получить completed_subs                      │
│     completed = { float(x) for x in subs }       │
│                                                  │
│  4. Проверка: sub_station_id ∉ completed         │
│                                                  │
│  5. UPDATE orders                                │
│     SET completed_subs = "1.1,1.2"               │
│     WHERE id = ?                                 │
│                                                  │
│  6. INSERT station_log                           │
│     result = 'SUB_COMPLETED'                     │
│                                                  │
│  7. COMMIT                                       │
└─────────────────────────────────────────────────┘
```

### Состояние после завершения подстанций
```
Завершена 1.1:
  completed_subs = "1.1"

Завершена 1.2:
  completed_subs = "1.1,1.2"  ← Теперь можно переместить заказ
```

---

## 4. Перемещение заказа

### Endpoint
```
POST /api/orders/<id>/move
```

### Логика перемещения

```
┌──────────────────────────────────────────────────────────┐
│  1. Проверка: order.status = 'production'                │
│     order.current_station IS NOT NULL                    │
│                                                          │
│  2. Если current_station — основная станция с подстанциями│
│     (например, 1.0):                                     │
│                                                          │
│     a. Получить все подстанции: [1.1, 1.2]               │
│                                                          │
│     b. Получить завершённые: {1.1, 1.2}                  │
│                                                          │
│     c. Если есть незавершённые:                          │
│        → ❌ "Сначала завершите подстанции: 1.1, 1.2"     │
│        → STOP                                            │
│                                                          │
│     d. Все подстанции завершены:                         │
│        → next_station = следующая ОСНОВНАЯ станция (2.0) │
│        → completed_subs очищается                        │
│                                                          │
│  3. Если current_station — обычная станция без подстанций│
│     (например, 2.0, 4.0):                                │
│     → next_station = следующая в списке (3.0)            │
│                                                          │
│  4. Если current_station — подстанция (не используется   │
│     для перемещения, подстанции только завершаются)       │
│     → next_station = следующая в списке                  │
│                                                          │
│  5. UPDATE station_log SET exited_at = NOW               │
│                                                          │
│  6. UPDATE orders SET current_station = next_station     │
│     completed_subs = '' (если перешли с основной станции)│
│                                                          │
│  7. INSERT station_log (entered_at = NOW)                │
│                                                          │
│  8. COMMIT                                               │
└──────────────────────────────────────────────────────────┘
```

### Полная последовательность прохождения заказа

```
Старт: buffer

1. launch → 1.0 (Приёмка)
   completed_subs = ""

2. complete-sub 1.1 → completed_subs = "1.1"
3. complete-sub 1.2 → completed_subs = "1.1,1.2"

4. move → 2.0 (Сортировка)
   completed_subs очищается → ""

5. move → 3.0 (Подготовка)
   completed_subs очищается → ""

6. complete-sub 3.1 → completed_subs = "3.1"

7. move → 4.0 (Сборка)
   completed_subs очищается → ""

8. move → 5.0 (Пайка)
9. move → 6.0 (Контроль)
10. move → 7.0 (Тестирование)
11. move → 8.0 (Упаковка)
12. move → 9.0 (Маркировка)
13. move → 10.0 (Отгрузка)
    → АВТО-ЗАВЕРШЕНИЕ: status = 'completed'
```

### Состояния заказа

| Статус | current_station | completed_subs | Описание |
|--------|----------------|----------------|----------|
| `buffer` | `NULL` | `""` | Создан, ожидает запуска |
| `production` | `1.0` | `""` | На основной станции |
| `production` | `1.0` | `"1.1"` | Подстанция 1.1 завершена |
| `production` | `1.0` | `"1.1,1.2"` | Все подстанции завершены, готов к перемещению |
| `production` | `2.0` | `""` | Перемещён на следующую станцию |
| `production` | `10.0` | `""` | На последней станции (авто-завершение) |
| `completed` | `NULL` | `""` | Заказ завершён |
| `cancelled` | `NULL` | `""` | Заказ отменён |

---

## 5. Автозавершение

Когда заказ достигает **последней станции** (10.0 — Отгрузка):

```
move → 10.0
  ↓
Controller.move_order():
  if current_station == last_station_id:
    complete_order(order_id)
    return "Order moved to final station and completed automatically"
```

---

## Диаграмма последовательности

```
Заказ → [1.0 Приёмка]
           │
           ├── [1.1 Приёмка 1.1] ← complete-sub
           └── [1.2 Приёмка 1.2] ← complete-sub
           │   (все подстанции завершены → move)
           ↓
        [2.0 Сортировка]
           │
           ↓
        [3.0 Подготовка]
           │
           └── [3.1 Подготовка 3.1] ← complete-sub
               (все подстанции завершены → move)
           ↓
        [4.0 Сборка]
           ↓
        [5.0 Пайка]
           ↓
        [6.0 Контроль]
           ↓
        [7.0 Тестирование]
           ↓
        [8.0 Упаковка]
           ↓
        [9.0 Маркировка]
           ↓
        [10.0 Отгрузка] → АВТО-ЗАВЕРШЕНИЕ ✓
```

---

## Блокировки и проверки

### Запрет перемещения
```
Заказ на 1.0, подстанции не завершены:
  move → ❌ "Сначала завершите подстанции: 1.1, 1.2"
```

### Разрешение перемещения
```
Заказ на 1.0, все подстанции завершены:
  move → ✅ Переход на 2.0
```

### Защита от повторного завершения
```
complete-sub 1.1 (уже завершена):
  → ❌ "Sub-station already completed"
```

### Защита от некорректного завершения
```
complete-sub 3.1, но заказ на 1.0:
  → ❌ "Order is not at the parent station"
```
