# Инструкция по работе с удалённым репозиторием

## Репозиторий

- **URL:** https://github.com/MaratSharf/stend
- **Remote:** `origin` → `https://github.com/MaratSharf/stend.git`
- **Ветки:**
  - `main` — основная ветка
  - `mes-system-production-line-da32a` — ветка разработки MES (текущая)

---

## 1. Первичная настройка

### Клонирование репозитория
```bash
git clone https://github.com/MaratSharf/stend.git
cd stend
```

### Проверка текущего состояния
```bash
git status          # Изменённые файлы и текущая ветка
git remote -v       # Удалённые репозитории
git branch -a       # Все ветки (локальные + удалённые)
git log --oneline -5 # Последние 5 коммитов
```

---

## 2. Основные команды

### Посмотреть изменения
```bash
git diff                    # Несохранённые изменения
git diff HEAD               # Все изменения (включая staged)
git diff --staged           # Только staged изменения
git log -n 3                # Последние 3 коммита
```

### Добавить файлы в коммит
```bash
git add .                   # Добавить все изменения
git add mes_production/utils/database.py  # Конкретный файл
git add mes_production/     # Все файлы в директории
```

### Сделать коммит
```bash
git commit -m "описание изменений"
```

### Отправить на удалённый репозиторий
```bash
git push                    # Push текущей ветки в origin
git push origin mes-system-production-line-da32a  # Явный push
```

### Получить изменения с удалённого репозитория
```bash
git fetch                   # Скачать без слияния
git pull                    # Скачать и слить
git pull origin main        # Pull из конкретной ветки
```

---

## 3. Работа с ветками

### Создать новую ветку
```bash
git checkout -b feature-new-name    # Создать и переключиться
git switch -c feature-new-name      # Альтернатива (git 2.23+)
```

### Переключиться на ветку
```bash
git checkout main
git checkout mes-system-production-line-da32a
```

### Отправить новую ветку на удалённый репозиторий
```bash
git push -u origin feature-branch-name
```

### Удалить ветку (локально)
```bash
git branch -d feature-branch-name
```

### Удалить ветку (удалённо)
```bash
git push origin --delete feature-branch-name
```

---

## 4. Слияние веток

### Влить ветку в main
```bash
git checkout main
git pull origin main                # Убедиться что актуальна
git merge mes-system-production-line-da32a
git push origin main
```

### Влить main в свою ветку (обновить)
```bash
git checkout mes-system-production-line-da32a
git merge main
# или
git rebase main
```

---

## 5. Разрешение конфликтов

Если при `merge` или `pull` возник конфликт:

```bash
# 1. Посмотреть конфликтующие файлы
git status

# 2. Открыть файлы, исправить конфликты (маркеры <<<<<<<, =======, >>>>>>>)

# 3. Добавить исправленные файлы
git add mes_production/utils/database.py

# 4. Завершить слияние
git commit -m "Merge main into mes-system-production-line-da32a"

# 5. Отправить
git push
```

---

## 6. Отмена изменений

### Отменить изменения в файле (до git add)
```bash
git restore mes_production/utils/database.py
git checkout -- mes_production/utils/database.py   # Альтернатива
```

### Убрать файл из staged (после git add)
```bash
git restore --staged mes_production/utils/database.py
git reset HEAD mes_production/utils/database.py    # Альтернатива
```

### Отменить последний коммит (сохранить изменения)
```bash
git reset --soft HEAD~1
```

### Отменить последний коммит (удалить изменения)
```bash
git reset --hard HEAD~1
```

---

## 7. Текущее состояние проекта

```
stend/
├── README.md                          # Изменён
├── QWEN.md                            # Новый (untracked)
├── mes_production/
│   ├── utils/database.py              # Изменён (порядковые номера заказов)
│   ├── web/app.py                     # Изменён (путь к config.yaml)
│   ├── tests/test_database.py         # Изменён (обновлены тесты)
│   ├── README_RU.md                   # Новый (untracked)
│   └── .coverage                      # Новый (игнорируется в .gitignore)
└── ...
```

### Рекомендуемый следующий шаг
```bash
# Закоммитить изменения
git add mes_production/utils/database.py mes_production/web/app.py mes_production/tests/test_database.py README.md
git commit -m "feat: sequential order numbers (ORD-0001, ORD-0002) and fix config path resolution"

# Отправить на GitHub
git push origin mes-system-production-line-da32a
```

---

## 8. GitHub Pull Request (PR)

Когда изменения готовы к вливанию в `main`:

1. Перейти на https://github.com/MaratSharf/stend
2. Нажать **Compare & pull request**
3. Заполнить описание изменений
4. Выбрать `main` как target
5. Нажать **Create pull request**
6. После ревью — **Merge pull request**

Или через CLI:
```bash
gh pr create --base main --head mes-system-production-line-da32a --title "MES updates" --body "Description"
```

---

## 9. Аутентификация

### Через HTTPS (текущий метод)
GitHub запросит логин и пароль (или Personal Access Token):
```bash
git push
# Username: MaratSharf
# Password: ваш Personal Access Token
```

> ⚠️ GitHub больше не принимает пароль для git. Используйте [Personal Access Token](https://github.com/settings/tokens).

### Настроить кеширование учётных данных
```bash
# Windows — использовать Credential Manager
git config --global credential.helper manager
```

### Через SSH (альтернатива)
```bash
# Генерация ключа
ssh-keygen -t ed25519 -C "your_email@example.com"

# Добавить публичный ключ в GitHub: https://github.com/settings/keys

# Сменить remote на SSH
git remote set-url origin git@github.com:MaratSharf/stend.git
```
git remote set-url origin https://github.com/MaratSharf/stend.git