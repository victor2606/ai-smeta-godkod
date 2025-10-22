# Database Generation Guide

Руководство для пользователей, которые получили **только Docker образ и Excel файлы**, но **НЕ имеют готовой базы данных** `estimates.db`.

---

## 📋 Сценарий использования

**Ситуация:** Вы получили:
- ✅ Docker образ: `ghcr.io/victor2606/construction-estimator-mcp:latest`
- ✅ Исходные Excel файлы с расценками (например, `Сonstruction_Works_Rate_Schedule_*.xlsx`)
- ❌ НЕТ готовой базы данных `estimates.db`

**Задача:** Сгенерировать `estimates.db` из Excel файлов.

---

## 🎯 Два варианта генерации БД

### Вариант 1: Внутри Docker контейнера (рекомендуется)

**Преимущества:**
- Не нужно устанавливать Python локально
- Гарантированная совместимость версий
- Изолированная среда

### Вариант 2: Локально (требует Python 3.10+)

**Преимущества:**
- Быстрее (нет overhead Docker)
- Удобнее для отладки
- Доступ к промежуточным файлам

---

## 📦 Вариант 1: Генерация БД в Docker (РЕКОМЕНДУЕТСЯ)

### Шаг 1: Подготовка директорий

```bash
mkdir -p construction-estimator/{data/raw,data/processed,data/logs}
cd construction-estimator
```

### Шаг 2: Размещение Excel файлов

```bash
# Скопируйте полученные Excel файлы в data/raw/
cp /path/to/Сonstruction_Works_Rate_Schedule_*.xlsx ./data/raw/

# Проверьте
ls -lh ./data/raw/*.xlsx
```

**Ожидаемый результат:**
```
-rw-r--r--  1 user  staff   135M  Сonstruction_Works_Rate_Schedule_17102025_half.xlsx
```

### Шаг 3: Создание docker-compose файла для ETL

Создайте файл `docker-compose-etl.yml`:

```yaml
version: '3.8'

services:
  etl-processor:
    image: ghcr.io/victor2606/construction-estimator-mcp:latest
    container_name: construction-etl-processor

    # Override entrypoint to run ETL instead of MCP server
    entrypoint: ["python3", "-m", "src.etl.excel_to_sqlite"]

    volumes:
      # Mount raw data (Excel files) - read-only
      - ./data/raw:/app/data/raw:ro

      # Mount output directory for generated DB
      - ./data/processed:/app/data/processed

      # Mount logs directory
      - ./data/logs:/app/data/logs

    environment:
      - PYTHONUNBUFFERED=1
      - LOG_LEVEL=INFO

    # Remove container after completion
    restart: "no"
```

### Шаг 4: Запуск генерации БД

```bash
# Запустить ETL процесс
docker-compose -f docker-compose-etl.yml up

# Процесс покажет прогресс:
# [INFO] Loading Excel file: /app/data/raw/Сonstruction_Works_Rate_Schedule_*.xlsx
# [INFO] Processing 28,686 rates...
# [INFO] Processing 294,883 resources...
# [INFO] Creating FTS5 index...
# [INFO] Database saved to: /app/data/processed/estimates.db
# [INFO] ETL completed successfully!
```

**Время выполнения:** 2-5 минут (зависит от размера Excel)

### Шаг 5: Проверка результата

```bash
# Проверить что БД создана
ls -lh ./data/processed/estimates.db

# Должно показать:
# -rw-r--r--  1 user  staff   147M  estimates.db

# Проверить размер БД (должно быть ~150 MB)
du -sh ./data/processed/estimates.db
```

### Шаг 6: Очистка временного контейнера

```bash
# Удалить контейнер ETL процессора
docker-compose -f docker-compose-etl.yml down

# Опционально: удалить docker-compose-etl.yml
rm docker-compose-etl.yml
```

### Шаг 7: Запуск MCP сервера с новой БД

```bash
# Теперь используйте обычный docker-compose.yml
docker-compose up -d

# Проверить здоровье
curl http://localhost:8003/health

# Ожидаемый ответ:
# {"status": "healthy", "database": "connected", "rates_count": 28686}
```

---

## 💻 Вариант 2: Генерация БД локально

### Предварительные требования

- Python 3.10 или выше
- pip (package installer)
- ~2 GB свободного места на диске

### Шаг 1: Клонирование репозитория (опционально)

Если у вас нет исходников, только Docker образ:

```bash
# Извлечь исходники из Docker образа
docker create --name temp-extract ghcr.io/victor2606/construction-estimator-mcp:latest
docker cp temp-extract:/app/src ./src
docker rm temp-extract
```

Или клонировать из GitHub:

```bash
git clone https://github.com/victor2606/ai-smeta-godkod.git
cd ai-smeta-godkod
```

### Шаг 2: Установка зависимостей

```bash
# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# или
venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt
```

**Основные зависимости для ETL:**
- `pandas>=2.0.0`
- `openpyxl>=3.1.0`
- `tqdm>=4.65.0`
- `rich>=13.0.0`

### Шаг 3: Размещение Excel файлов

```bash
# Создать директории
mkdir -p data/raw data/processed data/logs

# Скопировать Excel файлы
cp /path/to/Сonstruction_Works_Rate_Schedule_*.xlsx data/raw/

# Проверить
ls -lh data/raw/*.xlsx
```

### Шаг 4: Запуск ETL процесса

```bash
# Вариант A: Через модуль Python
python3 -m src.etl.excel_to_sqlite

# Вариант B: Напрямую (если есть скрипт)
python3 build_database.py
```

**Прогресс выполнения:**
```
[INFO] 2025-10-22 10:00:00 - Starting ETL process
[INFO] Excel file: data/raw/Сonstruction_Works_Rate_Schedule_17102025_half.xlsx
[INFO] Loading workbook...
Processing rates: 100%|████████████████| 28686/28686 [00:30<00:00, 950.21it/s]
Processing resources: 100%|████████████| 294883/294883 [02:15<00:00, 2178.34it/s]
[INFO] Creating database tables...
[INFO] Inserting data into SQLite...
[INFO] Creating FTS5 search index...
[INFO] Creating indexes for performance...
[INFO] Database created: data/processed/estimates.db (147.2 MB)
[INFO] ETL completed in 3m 42s
```

### Шаг 5: Проверка БД

```bash
# Проверить размер
ls -lh data/processed/estimates.db

# Проверить структуру БД
sqlite3 data/processed/estimates.db "SELECT COUNT(*) FROM rates;"
# Должно вернуть: 28686

sqlite3 data/processed/estimates.db "SELECT COUNT(*) FROM resources;"
# Должно вернуть: 294883
```

### Шаг 6: Тестирование БД

```bash
# Запустить тесты
pytest tests/test_search_engine.py -v
pytest tests/test_cost_calculator.py -v

# Все тесты должны пройти: PASSED
```

---

## 🔍 Валидация сгенерированной БД

### Автоматическая проверка

Создайте скрипт `validate_database.py`:

```python
#!/usr/bin/env python3
"""
Validate generated estimates.db database
"""
import sqlite3
import sys

DB_PATH = "data/processed/estimates.db"

def validate_database():
    print(f"Validating database: {DB_PATH}")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check 1: Tables exist
        tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]

        required_tables = ['rates', 'resources', 'rates_fts']
        for table in required_tables:
            if table not in table_names:
                print(f"❌ Missing table: {table}")
                return False
        print(f"✅ All required tables exist: {required_tables}")

        # Check 2: Rates count
        rates_count = cursor.execute("SELECT COUNT(*) FROM rates").fetchone()[0]
        if rates_count < 20000:
            print(f"❌ Too few rates: {rates_count} (expected ~28,686)")
            return False
        print(f"✅ Rates count: {rates_count:,}")

        # Check 3: Resources count
        resources_count = cursor.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
        if resources_count < 200000:
            print(f"❌ Too few resources: {resources_count} (expected ~294,883)")
            return False
        print(f"✅ Resources count: {resources_count:,}")

        # Check 4: FTS index
        fts_count = cursor.execute("SELECT COUNT(*) FROM rates_fts").fetchone()[0]
        if fts_count != rates_count:
            print(f"❌ FTS index mismatch: {fts_count} vs {rates_count}")
            return False
        print(f"✅ FTS index populated: {fts_count:,} entries")

        # Check 5: Sample search
        sample = cursor.execute(
            "SELECT rate_code, rate_full_name FROM rates LIMIT 1"
        ).fetchone()
        print(f"✅ Sample rate: {sample[0]} - {sample[1][:50]}...")

        # Check 6: Database size
        import os
        db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)
        if db_size_mb < 100 or db_size_mb > 300:
            print(f"⚠️  Unusual database size: {db_size_mb:.1f} MB (expected ~150 MB)")
        else:
            print(f"✅ Database size: {db_size_mb:.1f} MB")

        conn.close()
        print("\n🎉 Database validation PASSED!")
        return True

    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False

if __name__ == "__main__":
    success = validate_database()
    sys.exit(0 if success else 1)
```

Запуск:
```bash
python3 validate_database.py
```

### Ручная проверка через sqlite3

```bash
# Открыть БД в sqlite3
sqlite3 data/processed/estimates.db

# Проверить схему
.schema rates

# Проверить количество записей
SELECT COUNT(*) FROM rates;
SELECT COUNT(*) FROM resources;

# Проверить FTS поиск
SELECT rate_code, rate_full_name
FROM rates_fts
WHERE rates_fts MATCH 'перегородки гипсокартон'
LIMIT 5;

# Выйти
.quit
```

---

## 🐛 Troubleshooting

### Проблема 1: ETL контейнер падает с ошибкой "Excel file not found"

**Причина:** Excel файл не смонтирован в `/app/data/raw/`

**Решение:**
```bash
# Проверить что файл существует локально
ls -la ./data/raw/*.xlsx

# Проверить volume mount в docker-compose-etl.yml:
volumes:
  - ./data/raw:/app/data/raw:ro  # Должен быть правильный путь

# Пересоздать контейнер
docker-compose -f docker-compose-etl.yml down
docker-compose -f docker-compose-etl.yml up
```

### Проблема 2: "PermissionError: cannot write to /app/data/processed"

**Причина:** Недостаточно прав на запись в volume

**Решение:**
```bash
# Дать права на запись
chmod 777 ./data/processed

# Или изменить владельца (Linux/macOS)
sudo chown -R $(id -u):$(id -g) ./data/processed
```

### Проблема 3: БД создана, но размер 0 байт или очень маленький

**Причина:** ETL процесс завершился с ошибкой

**Решение:**
```bash
# Посмотреть логи контейнера
docker-compose -f docker-compose-etl.yml logs

# Удалить битую БД
rm ./data/processed/estimates.db

# Запустить заново с отладкой
docker-compose -f docker-compose-etl.yml up --force-recreate
```

### Проблема 4: "Memory error" при обработке большого Excel

**Причина:** Недостаточно RAM

**Решение:**
```bash
# Увеличить memory limit для Docker
# В docker-compose-etl.yml добавить:
services:
  etl-processor:
    mem_limit: 4g  # Увеличить до 4GB

# Или обработать Excel по частям (chunk processing)
# Это уже встроено в ExcelLoader(chunk_size=10000)
```

### Проблема 5: Локальный Python не находит модуль `src.etl`

**Причина:** Неправильная структура пакетов

**Решение:**
```bash
# Создать __init__.py файлы
touch src/__init__.py
touch src/etl/__init__.py

# Установить проект в editable mode
pip install -e .

# Или запустить через PYTHONPATH
PYTHONPATH=. python3 -m src.etl.excel_to_sqlite
```

---

## 📊 Сравнение вариантов

| Критерий | Docker (Вариант 1) | Локально (Вариант 2) |
|----------|-------------------|----------------------|
| **Простота** | ⭐⭐⭐⭐⭐ Очень просто | ⭐⭐⭐ Средне |
| **Скорость** | ⭐⭐⭐⭐ Быстро | ⭐⭐⭐⭐⭐ Очень быстро |
| **Требования** | Только Docker | Python 3.10+ |
| **Изоляция** | ✅ Полная | ❌ Зависит от системы |
| **Отладка** | ⭐⭐⭐ Сложнее | ⭐⭐⭐⭐⭐ Проще |
| **Воспроизводимость** | ✅ 100% | ⚠️ Зависит от версий |

**Рекомендация:** Используйте **Вариант 1 (Docker)** если:
- У вас нет опыта с Python
- Нужна гарантированная воспроизводимость
- Не хотите устанавливать зависимости локально

Используйте **Вариант 2 (локально)** если:
- Вы разработчик и хотите модифицировать ETL
- Нужна максимальная скорость
- Нужен доступ к промежуточным файлам для отладки

---

## 📚 Дополнительная информация

### Структура Excel файла (требования)

**Обязательные колонки:**
- `Расценка | Код` - Код расценки (например, "10-05-001-01")
- `Расценка | Исходное наименование` - Описание работы
- `Расценка | Ед. изм.` - Единица измерения (м², м³, т, шт)
- `Тип строки` - Тип записи (rate/resource)
- `Ресурс | Код` - Код ресурса
- `Ресурс | Стоимость (руб.)` - Стоимость ресурса
- `Прайс | АбстРесурс | Сметная цена текущая_median` - Медианная цена

**Формат файла:**
- `.xlsx` (Excel 2007+)
- Кодировка: UTF-8
- Размер: до 500 MB поддерживается

### Время обработки

Примерное время генерации БД:

| Размер Excel | Количество строк | Время (Docker) | Время (локально) |
|--------------|-----------------|----------------|------------------|
| 50 MB | ~50,000 | 1-2 мин | 30-60 сек |
| 135 MB | ~150,000 | 3-5 мин | 2-3 мин |
| 300 MB | ~350,000 | 8-12 мин | 5-8 мин |

### Требования к ресурсам

**Минимальные:**
- RAM: 2 GB
- Disk: 500 MB свободного места
- CPU: 2 cores

**Рекомендуемые:**
- RAM: 4 GB
- Disk: 2 GB свободного места
- CPU: 4 cores

---

## 🔄 Обновление существующей БД

Если у вас уже есть БД, но нужно обновить с новыми данными:

```bash
# Создать backup старой БД
cp data/processed/estimates.db data/processed/estimates_backup_$(date +%Y%m%d).db

# Удалить старую БД
rm data/processed/estimates.db

# Запустить ETL заново (любой из вариантов выше)

# Проверить новую БД
sqlite3 data/processed/estimates.db "SELECT COUNT(*) FROM rates;"

# Если что-то пошло не так, восстановить из backup
# cp data/processed/estimates_backup_YYYYMMDD.db data/processed/estimates.db
```

---

## ✅ Checklist для пользователя

Перед запуском MCP сервера убедитесь:

- [ ] Excel файл размещён в `./data/raw/`
- [ ] Размер Excel файла ~100-300 MB
- [ ] ETL процесс завершился без ошибок
- [ ] Файл `./data/processed/estimates.db` создан
- [ ] Размер БД ~100-200 MB
- [ ] Валидация БД пройдена (28,686 rates, 294,883 resources)
- [ ] Тестовый поиск работает

После генерации БД можете переходить к [FIRST_TIME_SETUP.md](./FIRST_TIME_SETUP.md) для запуска MCP сервера.

---

## 📞 Поддержка

Если возникли проблемы:
1. Проверьте логи: `docker-compose -f docker-compose-etl.yml logs`
2. Запустите валидацию: `python3 validate_database.py`
3. Изучите [Troubleshooting](#-troubleshooting) секцию
4. Создайте issue на GitHub с логами

---

**Made with ❤️ for construction cost estimation**
