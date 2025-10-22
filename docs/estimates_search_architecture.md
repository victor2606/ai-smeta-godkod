# Архитектура системы поиска расценок в сметной документации

**Дата:** 18 октября 2025
**Объем данных:** 740,000 строк × 73 колонки (полная БД) / 96 строк × 73 колонки (текущий пример)
**Цель:** Создать систему быстрого поиска и расчета стоимости строительных работ на основе естественноязыковых запросов

---

## 📊 Структура данных (результаты анализа)

### Иерархия данных

```
Категория работ (3 типа)
└── Сборник (3 уникальных)
    └── Отдел (3 уникальных)
        └── Раздел (6 уникальных)
            └── Подраздел
                └── Таблица
                    └── РАСЦЕНКА (4 в примере, ~20-30K в полной БД)
                        ├── Состав работ (10-35 строк текста)
                        ├── Ресурсы (17-56 строк)
                        └── Абстрактные ресурсы (2-5 строк)
```

### Ключевые поля для поиска

| Поле | Пример | Назначение |
|------|--------|------------|
| `Расценка \| Код` | `10-05-001-01` | Уникальный идентификатор |
| `Расценка \| Исходное наименование` | `Устройство перегородок из гипсокартонных листов (ГКЛ) с одинарным металлическим каркасом...` | Полное описание работы |
| `Расценка \| Конечное наименование` | `глухих` | Уточнение/спецификация |
| `Расценка \| Ед. изм.` | `100 м2` | Базовая единица измерения |
| `Общая стоимость по позиции` | `138,320.18 руб.` | Стоимость за базовую единицу |
| `Сумма стоимости материалов` | `35,118.80 руб.` | Только материалы |
| `Сумма стоимости ресурсов` | `103,201.38 руб.` | Работы + техника |

### Структура одной расценки

**Пример: 10-05-001-01 (Перегородки из ГКЛ)**

- **Базовая единица:** 100 м²
- **Общая стоимость:** 138,320.18 руб.
- **Цена за 1 м²:** 1,383.20 руб.

**Состав работ (10 операций):**
1. Разметка проектного положения металлического каркаса
2. Наклейка уплотнительной ленты на профили
3. Установка и крепление направляющих профилей
4. Установка стоечных профилей
5. Устройство горизонтальных вставок
6. Наклейка разделительной ленты
7. Установка гипсокартонных листов с креплением
8. Укладка изоляционного материала
9. Заделка швов с армирующей лентой
10. Грунтование поверхности

**Ресурсы (17 позиций):**
- Труд: 98 чел-ч × 598.47 руб. = 58,650.06 руб.
- Материалы: ГКЛ листы, профили, крепеж, шпатлевка и т.д.
- Техника: кран 16т (0.52 маш-ч), автомобиль (0.21 маш-ч)
- Электроэнергия: 2.764 кВт·ч × 7.16 руб. = 19.79 руб.

---

## 🎯 Пользовательский сценарий

**Запрос пользователя:**
> "Сколько будет стоить устройство 150 м² перегородок из ГКЛ в один слой?"

**Ожидаемый результат:**
```
Найдена расценка: 10-05-001-01
Наименование: Устройство перегородок из гипсокартонных листов (ГКЛ)
              с одинарным металлическим каркасом и однослойной обшивкой
              с обеих сторон (глухих)

Базовая стоимость: 138,320.18 руб. за 100 м²
Стоимость за 1 м²: 1,383.20 руб.

Расчет для 150 м²:
= (138,320.18 / 100) × 150
= 207,480.27 руб.

Из них:
- Материалы: 52,677.00 руб. (25%)
- Работы и техника: 154,803.27 руб. (75%)
```

---

## 🏗️ Варианты архитектуры

### Вариант 1: SQLite + FTS5 (Full-Text Search)

**⭐ РЕКОМЕНДУЕМЫЙ БАЗОВЫЙ ВАРИАНТ**

#### Архитектура

```
┌─────────────────┐
│  Excel (740K)   │
│   73 columns    │
└────────┬────────┘
         │ ETL (Python)
         ↓
┌─────────────────────────────┐
│   SQLite Database (.db)     │
├─────────────────────────────┤
│                             │
│  ┌───────────────────────┐  │
│  │  rates (aggregated)   │  │
│  │  ~20-30K rows         │  │
│  └───────────────────────┘  │
│                             │
│  ┌───────────────────────┐  │
│  │  rates_fts (FTS5)     │  │
│  │  Full-text index      │  │
│  └───────────────────────┘  │
│                             │
│  ┌───────────────────────┐  │
│  │  resources (detail)   │  │
│  │  ~500K rows           │  │
│  └───────────────────────┘  │
└─────────────────────────────┘
         │
         ↓
┌─────────────────┐
│  Python API     │
│  search_rate()  │
│  calculate()    │
└─────────────────┘
```

#### Структура таблиц

```sql
-- Основная таблица расценок (агрегированная: 1 расценка = 1 строка)
CREATE TABLE rates (
    id INTEGER PRIMARY KEY,
    rate_code TEXT UNIQUE NOT NULL,           -- 10-05-001-01

    -- Иерархия
    category TEXT,                             -- СТРОИТЕЛЬНЫЕ РАБОТЫ
    collection_code INTEGER,                   -- 1
    collection_name TEXT,                      -- ГЭСНм-2020
    department_code TEXT,                      -- 10
    department_name TEXT,                      -- Конструкции из гипсокартонных листов
    section_name TEXT,                         -- Перегородки

    -- Описание работы
    rate_full_name TEXT NOT NULL,             -- Устройство перегородок...
    rate_short_name TEXT,                      -- глухих
    composition_text TEXT,                     -- JSON массив работ

    -- Единицы измерения
    unit_measure_full TEXT,                    -- "100 м2"
    unit_quantity REAL NOT NULL,               -- 100
    unit_type TEXT NOT NULL,                   -- "м2"

    -- Стоимости
    total_cost REAL NOT NULL,                  -- 138320.18
    materials_cost REAL,                       -- 35118.80
    resources_cost REAL,                       -- 103201.38

    -- Обоснования
    overhead_rate TEXT,                        -- Пр/812-001.1 (НР)
    profit_rate TEXT,                          -- Пр/774-001.1 (СП)

    -- Для полнотекстового поиска
    search_text TEXT,                          -- Конкатенация всех текстовых полей

    -- Метаданные
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы
CREATE INDEX idx_rate_code ON rates(rate_code);
CREATE INDEX idx_unit_type ON rates(unit_type);
CREATE INDEX idx_category ON rates(category);

-- FTS5 для полнотекстового поиска
CREATE VIRTUAL TABLE rates_fts USING fts5(
    rate_code,
    rate_full_name,
    rate_short_name,
    search_text,
    content='rates',
    tokenize='unicode61 remove_diacritics 2'
);

-- Триггеры для синхронизации FTS
CREATE TRIGGER rates_ai AFTER INSERT ON rates BEGIN
    INSERT INTO rates_fts(rowid, rate_code, rate_full_name, rate_short_name, search_text)
    VALUES (new.id, new.rate_code, new.rate_full_name, new.rate_short_name, new.search_text);
END;

-- Таблица ресурсов (детализация)
CREATE TABLE resources (
    id INTEGER PRIMARY KEY,
    rate_id INTEGER NOT NULL,
    resource_type TEXT,                        -- Ресурс, Абстрактный ресурс
    resource_code TEXT,                        -- 01.7.06.01-0042
    resource_name TEXT,                        -- Ленты эластичные...
    quantity REAL,                             -- 126.0
    unit TEXT,                                 -- м
    price_per_unit REAL,                       -- 7.73
    total_price REAL,                          -- 973.98

    FOREIGN KEY (rate_id) REFERENCES rates(id)
);

CREATE INDEX idx_resources_rate ON resources(rate_id);
```

#### Пример SQL-запросов

```sql
-- 1. Полнотекстовый поиск по описанию
SELECT
    r.rate_code,
    r.rate_full_name || ' (' || r.rate_short_name || ')' AS description,
    r.unit_measure_full,
    r.total_cost,
    r.unit_quantity,
    ROUND(r.total_cost / r.unit_quantity, 2) AS cost_per_unit,
    rates_fts.rank
FROM rates r
JOIN rates_fts ON rates_fts.rowid = r.id
WHERE rates_fts MATCH 'перегородк* гипсокартон* глух*'
ORDER BY rates_fts.rank
LIMIT 10;

-- 2. Расчет стоимости для заданного объема
SELECT
    rate_code,
    rate_full_name,
    unit_measure_full,
    total_cost AS base_cost,
    ROUND((total_cost / unit_quantity) * :user_quantity, 2) AS calculated_cost,
    ROUND((materials_cost / unit_quantity) * :user_quantity, 2) AS materials_cost_calc,
    ROUND((resources_cost / unit_quantity) * :user_quantity, 2) AS resources_cost_calc
FROM rates
WHERE rate_code = '10-05-001-01'
  AND unit_type = 'м2';

-- 3. Fuzzy search по коду расценки
SELECT *
FROM rates
WHERE rate_code LIKE '10-05%'
ORDER BY rate_code;

-- 4. Детализация ресурсов для расценки
SELECT
    res.resource_code,
    res.resource_name,
    res.quantity || ' ' || res.unit AS quantity_full,
    res.price_per_unit,
    res.total_price
FROM resources res
JOIN rates r ON res.rate_id = r.id
WHERE r.rate_code = '10-05-001-01'
  AND res.resource_type = 'Ресурс'
ORDER BY res.total_price DESC;
```

#### ETL процесс (Python)

```python
import pandas as pd
import sqlite3
import re
import json

def extract_unit_info(unit_str):
    """Извлекает число и единицу измерения из строки типа '100 м2'"""
    if pd.isna(unit_str):
        return None, None
    match = re.match(r'(\d+\.?\d*)\s*(.+)', str(unit_str))
    if match:
        return float(match.group(1)), match.group(2).strip()
    return None, unit_str

def aggregate_rate(rate_df):
    """Агрегирует все строки одной расценки в одну запись"""
    first_row = rate_df.iloc[0]

    # Собираем состав работ
    composition = rate_df[rate_df['Тип строки'] == 'Состав работ']['Состав работ | Текст'].dropna().tolist()

    # Извлекаем единицы измерения
    qty, unit = extract_unit_info(first_row['Расценка | Ед. изм.'])

    # Создаем поисковый текст
    search_text = ' '.join(filter(None, [
        first_row['Расценка | Исходное наименование'],
        first_row['Расценка | Конечное наименование'],
        first_row['Раздел | Имя'],
        ' '.join(composition)
    ]))

    return {
        'rate_code': first_row['Расценка | Код'],
        'category': first_row['Категория | Тип'],
        'collection_code': first_row['Сборник | Код'],
        'collection_name': first_row['Сборник | Имя'],
        'department_code': first_row['Отдел | Код'],
        'department_name': first_row['Отдел | Имя'],
        'section_name': first_row['Раздел | Имя'],
        'rate_full_name': first_row['Расценка | Исходное наименование'],
        'rate_short_name': first_row['Расценка | Конечное наименование'],
        'composition_text': json.dumps(composition, ensure_ascii=False),
        'unit_measure_full': first_row['Расценка | Ед. изм.'],
        'unit_quantity': qty,
        'unit_type': unit,
        'total_cost': first_row['Общая стоимость по позиции'],
        'materials_cost': first_row['Сумма стоимости материалов по позиции'],
        'resources_cost': first_row['Сумма стоимости ресурсов по позиции'],
        'overhead_rate': first_row['Обоснование | НР'],
        'profit_rate': first_row['Обоснование | СП'],
        'search_text': search_text
    }

# ETL Pipeline
df = pd.read_excel('estimates.xlsx')
conn = sqlite3.connect('estimates.db')

# Агрегируем расценки
aggregated_rates = []
for rate_code, group in df.groupby('Расценка | Код'):
    aggregated_rates.append(aggregate_rate(group))

rates_df = pd.DataFrame(aggregated_rates)
rates_df.to_sql('rates', conn, if_exists='replace', index=False)

# Сохраняем детальные ресурсы
resources_df = df[df['Тип строки'] == 'Ресурс'][[
    'Расценка | Код', 'Ресурс | Код', 'Ресурс | Наименование',
    'Ресурс | Количество', 'Ресурс | Ед. изм.',
    'Ресурс | Цена за ед. (руб., текущ.)', 'Ресурс | Стоимость (руб.)'
]]
resources_df.to_sql('resources', conn, if_exists='replace', index=False)

conn.close()
```

#### API для поиска

```python
import sqlite3

class EstimatesSearchAPI:
    def __init__(self, db_path='estimates.db'):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def search_rates(self, query: str, limit: int = 10):
        """Полнотекстовый поиск расценок"""
        # Преобразуем запрос в FTS-совместимый формат
        fts_query = ' '.join([f'{word}*' for word in query.split()])

        cursor = self.conn.execute("""
            SELECT
                r.rate_code,
                r.rate_full_name,
                r.rate_short_name,
                r.unit_measure_full,
                r.total_cost,
                r.unit_quantity,
                r.unit_type,
                ROUND(r.total_cost / r.unit_quantity, 2) AS cost_per_unit,
                rates_fts.rank
            FROM rates r
            JOIN rates_fts ON rates_fts.rowid = r.id
            WHERE rates_fts MATCH ?
            ORDER BY rates_fts.rank
            LIMIT ?
        """, (fts_query, limit))

        return [dict(row) for row in cursor.fetchall()]

    def calculate_cost(self, rate_code: str, quantity: float):
        """Рассчитывает стоимость для заданного объема"""
        cursor = self.conn.execute("""
            SELECT
                rate_code,
                rate_full_name,
                rate_short_name,
                unit_measure_full,
                unit_type,
                total_cost,
                materials_cost,
                resources_cost,
                unit_quantity,
                ROUND((total_cost / unit_quantity) * ?, 2) AS calculated_cost,
                ROUND((materials_cost / unit_quantity) * ?, 2) AS materials_calc,
                ROUND((resources_cost / unit_quantity) * ?, 2) AS resources_calc
            FROM rates
            WHERE rate_code = ?
        """, (quantity, quantity, quantity, rate_code))

        result = cursor.fetchone()
        return dict(result) if result else None

    def get_resources(self, rate_code: str):
        """Получает детализацию ресурсов"""
        cursor = self.conn.execute("""
            SELECT
                res.resource_code,
                res.resource_name,
                res.quantity,
                res.unit,
                res.price_per_unit,
                res.total_price
            FROM resources res
            JOIN rates r ON res.rate_id = r.id
            WHERE r.rate_code = ?
            ORDER BY res.total_price DESC
        """, (rate_code,))

        return [dict(row) for row in cursor.fetchall()]

# Пример использования
api = EstimatesSearchAPI()

# Поиск
results = api.search_rates("перегородки гипсокартон глухие")
for r in results:
    print(f"{r['rate_code']}: {r['rate_full_name']} ({r['rate_short_name']})")
    print(f"  Цена: {r['cost_per_unit']} руб/{r['unit_type']}")

# Расчет
cost_info = api.calculate_cost("10-05-001-01", 150)
print(f"Стоимость 150 {cost_info['unit_type']}: {cost_info['calculated_cost']} руб.")
```

#### Преимущества

✅ **Простота:**
- Один файл базы данных
- Встроенная в Python (sqlite3)
- Не требует установки серверов

✅ **Скорость:**
- FTS5 обрабатывает 20-30K расценок за <100ms
- Индексы ускоряют поиск по коду
- Агрегированные данные = меньше JOIN'ов

✅ **Портативность:**
- Можно передать файл .db
- Работает на любой ОС
- Backup = копирование файла

✅ **Гибкость:**
- SQL для любых аналитических запросов
- Легко добавлять новые поля
- Поддержка транзакций

✅ **Размер:**
- 740K строк → ~20-30K расценок → ~50-100MB БД
- С FTS индексами: ~150-200MB

#### Недостатки

⚠️ **Ограничения FTS5:**
- Слабая морфология для русского языка (нужны расширения)
- Нет семантического поиска (только keyword matching)
- Не понимает синонимы ("ГКЛ" ≠ "гипсокартон" без настройки)

⚠️ **Масштабируемость:**
- Не подходит для >10M записей
- Однопоточная запись
- Один файл = одна точка отказа

⚠️ **Отсутствие AI:**
- Не понимает контекст запроса
- Нужно точно формулировать поисковые запросы
- Нет ранжирования по релевантности (кроме базового)

#### Когда использовать

✅ Идеально для:
- Небольших и средних баз (до 1M расценок)
- Локальных приложений
- Быстрых прототипов
- Offline-работы
- Встраивания в десктопные приложения

---

### Вариант 2: PostgreSQL + pgvector + pg_trgm

**⚡ ДЛЯ ВЫСОКОНАГРУЖЕННЫХ СИСТЕМ**

#### Архитектура

```
┌─────────────────┐
│  Excel (740K)   │
└────────┬────────┘
         │ ETL
         ↓
┌──────────────────────────────────────┐
│      PostgreSQL Database             │
├──────────────────────────────────────┤
│                                      │
│  ┌────────────────────────────────┐  │
│  │  rates (main table)            │  │
│  │  + GIN index (pg_trgm)         │  │
│  │  + IVFFLAT index (pgvector)    │  │
│  └────────────────────────────────┘  │
│                                      │
│  ┌────────────────────────────────┐  │
│  │  resources (details)           │  │
│  └────────────────────────────────┘  │
└──────────────────────────────────────┘
         │
         ↓
┌─────────────────────┐
│  Embedding Service  │
│  (text-embedding-3) │
└─────────────────────┘
```

#### Структура таблиц

```sql
-- Включаем расширения
CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- Триграммы для fuzzy search
CREATE EXTENSION IF NOT EXISTS vector;         -- Векторы для семантического поиска

-- Основная таблица
CREATE TABLE rates (
    id SERIAL PRIMARY KEY,
    rate_code VARCHAR(50) UNIQUE NOT NULL,

    -- Описание
    rate_full_name TEXT NOT NULL,
    rate_short_name VARCHAR(255),
    search_text TEXT NOT NULL,

    -- Единицы
    unit_quantity NUMERIC(10,2) NOT NULL,
    unit_type VARCHAR(20) NOT NULL,

    -- Стоимости
    total_cost NUMERIC(12,2) NOT NULL,
    materials_cost NUMERIC(12,2),
    resources_cost NUMERIC(12,2),

    -- Векторное представление для семантического поиска
    embedding vector(384),  -- Размерность зависит от модели

    -- Метаданные
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для быстрого поиска
CREATE INDEX idx_rate_code ON rates(rate_code);
CREATE INDEX idx_unit_type ON rates(unit_type);

-- GIN индекс для pg_trgm (fuzzy text search)
CREATE INDEX idx_search_text_trgm ON rates USING GIN (search_text gin_trgm_ops);

-- IVFFLAT индекс для векторного поиска
CREATE INDEX idx_embedding_ivfflat ON rates
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);  -- Настраивается под размер данных
```

#### Примеры запросов

```sql
-- 1. Fuzzy search с триграммами (опечатки, похожие слова)
SELECT
    rate_code,
    rate_full_name,
    rate_short_name,
    similarity(search_text, 'перигородки гипсакартон') AS sim
FROM rates
WHERE search_text % 'перигородки гипсакартон'  -- % оператор для сходства
ORDER BY sim DESC
LIMIT 10;

-- 2. Семантический поиск (понимает смысл)
SELECT
    rate_code,
    rate_full_name,
    1 - (embedding <=> :query_embedding::vector) AS similarity
FROM rates
ORDER BY embedding <=> :query_embedding::vector
LIMIT 10;

-- 3. Гибридный поиск (текст + семантика)
WITH text_search AS (
    SELECT id, rate_code,
           similarity(search_text, :query) * 0.3 AS text_score
    FROM rates
    WHERE search_text % :query
),
vector_search AS (
    SELECT id, rate_code,
           (1 - (embedding <=> :query_embedding::vector)) * 0.7 AS vector_score
    FROM rates
    ORDER BY embedding <=> :query_embedding::vector
    LIMIT 50
)
SELECT
    r.rate_code,
    r.rate_full_name,
    COALESCE(ts.text_score, 0) + COALESCE(vs.vector_score, 0) AS combined_score
FROM rates r
LEFT JOIN text_search ts ON r.id = ts.id
LEFT JOIN vector_search vs ON r.id = vs.id
WHERE ts.id IS NOT NULL OR vs.id IS NOT NULL
ORDER BY combined_score DESC
LIMIT 10;
```

#### ETL с векторизацией

```python
import openai
import psycopg2
from psycopg2.extras import execute_values

def get_embedding(text: str, model="text-embedding-3-small"):
    """Получает векторное представление текста"""
    response = openai.Embedding.create(
        input=text,
        model=model
    )
    return response['data'][0]['embedding']

def load_to_postgres(rates_df, conn_string):
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()

    # Подготовка данных с embeddings
    data = []
    for _, row in rates_df.iterrows():
        # Создаем текст для векторизации
        search_text = f"{row['rate_full_name']} {row['rate_short_name']}"

        # Получаем embedding
        embedding = get_embedding(search_text)

        data.append((
            row['rate_code'],
            row['rate_full_name'],
            row['rate_short_name'],
            search_text,
            row['unit_quantity'],
            row['unit_type'],
            row['total_cost'],
            row['materials_cost'],
            row['resources_cost'],
            embedding
        ))

    # Batch insert
    execute_values(
        cursor,
        """
        INSERT INTO rates
        (rate_code, rate_full_name, rate_short_name, search_text,
         unit_quantity, unit_type, total_cost, materials_cost,
         resources_cost, embedding)
        VALUES %s
        """,
        data
    )

    conn.commit()
    cursor.close()
    conn.close()
```

#### Преимущества

✅ **Мощный поиск:**
- Триграммы находят опечатки
- Векторы понимают семантику
- Гибридный подход = максимальная точность

✅ **Масштабируемость:**
- Миллионы записей
- Репликация master-slave
- Партиционирование таблиц

✅ **Enterprise-функции:**
- ACID транзакции
- Полноценный SQL
- Расширенная аналитика

✅ **Производительность:**
- Параллельные запросы
- Кэширование
- Оптимизатор запросов

#### Недостатки

⚠️ **Сложность:**
- Требует установки и настройки сервера
- Нужен DevOps для продакшена
- Резервное копирование сложнее

⚠️ **Стоимость embeddings:**
- OpenAI API: ~$0.02 за 1K расценок (text-embedding-3-small)
- Для 30K расценок: ~$0.60 единоразово
- Можно использовать локальные модели (sentence-transformers)

⚠️ **Требования к ресурсам:**
- RAM: минимум 4GB для индексов
- Disk: ~1GB для 30K расценок с векторами

#### Когда использовать

✅ Идеально для:
- Enterprise-систем
- Высокая нагрузка (>1000 запросов/сек)
- Нужна семантическая точность
- Распределенная команда
- Уже есть PostgreSQL в инфраструктуре

---

### Вариант 3: Elasticsearch / OpenSearch

**🔍 СПЕЦИАЛИЗИРОВАННЫЙ ПОИСКОВИК**

#### Архитектура

```
┌─────────────────┐
│  Excel (740K)   │
└────────┬────────┘
         │ Logstash / Python
         ↓
┌──────────────────────────────────────┐
│      Elasticsearch Cluster           │
├──────────────────────────────────────┤
│                                      │
│  ┌────────────────────────────────┐  │
│  │  Index: rates                  │  │
│  │  - Inverted index (full-text)  │  │
│  │  - kNN index (vectors)         │  │
│  │  - Aggregations bucket         │  │
│  └────────────────────────────────┘  │
│                                      │
│  Shards: 3 (распределено)            │
│  Replicas: 1 (дублировано)           │
└──────────────────────────────────────┘
         │
         ↓
┌─────────────────┐
│  REST API       │
│  (port 9200)    │
└─────────────────┘
```

#### Mapping (схема индекса)

```json
{
  "mappings": {
    "properties": {
      "rate_code": {
        "type": "keyword"
      },
      "rate_full_name": {
        "type": "text",
        "analyzer": "russian",
        "fields": {
          "keyword": {
            "type": "keyword"
          }
        }
      },
      "rate_short_name": {
        "type": "text",
        "analyzer": "russian"
      },
      "search_text": {
        "type": "text",
        "analyzer": "russian"
      },
      "unit_quantity": {
        "type": "float"
      },
      "unit_type": {
        "type": "keyword"
      },
      "total_cost": {
        "type": "float"
      },
      "materials_cost": {
        "type": "float"
      },
      "resources_cost": {
        "type": "float"
      },
      "embedding": {
        "type": "dense_vector",
        "dims": 384,
        "index": true,
        "similarity": "cosine"
      },
      "category": {
        "type": "keyword"
      },
      "department_name": {
        "type": "keyword"
      }
    }
  }
}
```

#### Примеры запросов

```python
from elasticsearch import Elasticsearch

es = Elasticsearch(['http://localhost:9200'])

# 1. Полнотекстовый поиск с fuzzy matching
query = {
    "query": {
        "multi_match": {
            "query": "перегородки гипсокартон",
            "fields": ["rate_full_name^3", "rate_short_name^2", "search_text"],
            "fuzziness": "AUTO",
            "type": "best_fields"
        }
    },
    "size": 10
}

results = es.search(index="rates", body=query)

# 2. Векторный поиск (kNN)
query_vector = get_embedding("перегородки из ГКЛ")

knn_query = {
    "knn": {
        "field": "embedding",
        "query_vector": query_vector,
        "k": 10,
        "num_candidates": 100
    }
}

results = es.search(index="rates", body=knn_query)

# 3. Гибридный поиск с фильтрами
hybrid_query = {
    "query": {
        "bool": {
            "must": [
                {
                    "multi_match": {
                        "query": "перегородки",
                        "fields": ["rate_full_name", "search_text"]
                    }
                }
            ],
            "filter": [
                {"term": {"unit_type": "м2"}},
                {"range": {"total_cost": {"gte": 100000, "lte": 200000}}}
            ]
        }
    },
    "knn": {
        "field": "embedding",
        "query_vector": query_vector,
        "k": 5,
        "num_candidates": 50
    },
    "size": 10
}

# 4. Агрегации (аналитика)
agg_query = {
    "size": 0,
    "aggs": {
        "avg_cost_by_unit": {
            "terms": {
                "field": "unit_type"
            },
            "aggs": {
                "avg_cost": {
                    "avg": {"field": "total_cost"}
                }
            }
        }
    }
}
```

#### Преимущества

✅ **Продвинутый поиск:**
- Морфология для русского языка
- Fuzzy matching из коробки
- Синонимы и стоп-слова
- Highlighting результатов

✅ **Масштабирование:**
- Горизонтальное (добавление нод)
- Шардирование данных
- Репликация для отказоустойчивости

✅ **Аналитика:**
- Aggregations (группировка, статистика)
- Kibana для визуализации
- Real-time анализ данных

✅ **Гибкость:**
- Динамические схемы
- Nested documents
- Parent-child relationships

#### Недостатки

⚠️ **Сложность:**
- Отдельный кластер
- Требует опыта DevOps
- Сложная настройка производительности

⚠️ **Ресурсы:**
- RAM: минимум 8GB (рекомендуется 16GB)
- Disk: ~3-5GB для 30K расценок
- CPU: 2+ ядра

⚠️ **Избыточность:**
- Для 740K строк это overkill
- Дорого в эксплуатации
- Долгий setup

⚠️ **Стоимость:**
- Elastic Cloud: от $95/месяц
- Или self-hosted (время DevOps)

#### Когда использовать

✅ Идеально для:
- >100K запросов/день
- Нужна real-time аналитика
- Сложные faceted-поиски
- Уже используется Elastic Stack
- Enterprise с большим бюджетом

❌ НЕ использовать для:
- Простых MVP
- Бюджетных проектов
- Небольших баз (<100K записей)

---

### Вариант 4: DuckDB (Аналитический подход)

**🦆 БЫСТРАЯ АНАЛИТИКА БЕЗ ETL**

#### Концепция

```
Excel/Parquet → DuckDB (in-process) → SQL запросы
     (не перемещается)
```

#### Пример использования

```python
import duckdb

# Подключаемся напрямую к файлу
conn = duckdb.connect()

# Читаем Excel напрямую
conn.execute("""
    CREATE TABLE rates AS
    SELECT * FROM read_excel('estimates.xlsx', sheet='Sheet1')
""")

# Или работаем с Parquet (быстрее)
conn.execute("""
    CREATE TABLE rates AS
    SELECT * FROM 'estimates.parquet'
""")

# Полнотекстовый поиск через LIKE + регулярки
query = """
    SELECT
        "Расценка | Код" as rate_code,
        "Расценка | Конечное наименование" as name,
        "Общая стоимость по позиции" as total_cost,
        regexp_extract("Расценка | Ед. изм.", '(\d+)') as unit_qty
    FROM rates
    WHERE
        "Расценка | Исходное наименование" LIKE '%перегородк%'
        AND "Расценка | Исходное наименование" LIKE '%гипсокартон%'
    GROUP BY
        "Расценка | Код",
        "Расценка | Конечное наименование",
        "Общая стоимость по позиции",
        "Расценка | Ед. изм."
    LIMIT 10
"""

results = conn.execute(query).fetchdf()
print(results)
```

#### Преимущества

✅ **Скорость:**
- Работает напрямую с файлами
- Columnar storage = быстрые агрегации
- Parallel query execution

✅ **Простота:**
- Встроенная в процесс (как SQLite)
- Не нужен отдельный сервер
- Знакомый SQL синтаксис

✅ **Аналитика:**
- Оконные функции
- CTEs (Common Table Expressions)
- Экспорт в Pandas/Parquet

#### Недостатки

⚠️ **Слабый поиск:**
- Нет FTS (только LIKE)
- Нет морфологии
- Нет векторного поиска

⚠️ **Производительность на повторах:**
- Каждый запрос = перечитывание файла
- Нет персистентных индексов (если не сохранить в .duckdb)

⚠️ **Не подходит для:**
- Production систем с высокой нагрузкой
- Сложных полнотекстовых запросов

#### Когда использовать

✅ Идеально для:
- Ad-hoc анализа данных
- Прототипирования
- Data science исследований
- Локальной работы с файлами

---

### 🚀 Вариант 5: ГИБРИД - SQLite FTS5 + Claude API Agent

**⭐ МАКСИМАЛЬНАЯ РЕКОМЕНДАЦИЯ: "БАЗА + МОЗГИ"**

#### Концепция

Комбинация структурированного хранения (SQLite) с интеллектуальной обработкой запросов (Claude API). Claude выступает как "интерпретатор намерений" пользователя.

#### Архитектура

```
                           ┌─────────────────────┐
                           │   User Query        │
                           │ (natural language)  │
                           └──────────┬──────────┘
                                      │
                                      ↓
                 ┌────────────────────────────────────┐
                 │     Claude Agent (Orchestrator)    │
                 │  - Intent analysis                 │
                 │  - Query parsing                   │
                 │  - Context understanding           │
                 │  - Response generation             │
                 └────┬──────────────────────────┬────┘
                      │                          │
         ┌────────────┘                          └───────────┐
         │                                                   │
         ↓                                                   ↓
┌─────────────────────┐                        ┌─────────────────────┐
│   Tools (MCP)       │                        │   SQLite + FTS5     │
│                     │                        │                     │
│ 1. search_rates()   │◄──────────────────────►│  • rates table      │
│    - FTS query      │                        │  • rates_fts        │
│    - Filters        │                        │  • resources        │
│                     │                        │  • indexes          │
│ 2. calculate_cost() │                        └─────────────────────┘
│    - Rate lookup    │
│    - Math calc      │
│                     │
│ 3. get_details()    │
│    - Resources      │
│    - Composition    │
│                     │
│ 4. compare_rates()  │
│    - Multi-rate     │
│    - Best match     │
└─────────────────────┘
         │
         ↓
┌─────────────────────┐
│  Formatted Answer   │
│  + Calculations     │
│  + Explanations     │
│  + Alternatives     │
└─────────────────────┘
```

#### Пример flow

**User:**
> "Сколько стоит сделать перегородки в офисе на 150 квадратов? Нужно два слоя гипсокартона с обеих сторон."

**Claude Agent (internal reasoning):**
1. Понимает намерение: расчет стоимости
2. Извлекает параметры:
   - Тип работы: перегородки
   - Материал: гипсокартон (ГКЛ)
   - Объем: 150 м²
   - Особенность: два слоя
3. Формирует запрос к БД: `search_rates("перегородки гипсокартон два слоя")`
4. Анализирует результаты (может быть несколько вариантов)
5. Вызывает `calculate_cost(rate_code, 150)` для каждого
6. Форматирует ответ с пояснениями

**Claude Agent (response):**
> Нашел подходящую расценку для перегородок с двухслойной обшивкой:
>
> **Расценка: 10-06-037-02**
> Облицовка стен по одинарному металлическому каркасу из потолочного профиля гипсокартонными листами двумя слоями с оконным проемом
>
> **Стоимость для 150 м²:**
> - Базовая цена: 187,616.18 руб. за 100 м²
> - Цена за 1 м²: 1,876.16 руб.
> - **Итого: 281,424.27 руб.**
>
> Из них:
> - Материалы: ~70,356 руб.
> - Работы и техника: ~211,068 руб.
>
> **Состав работ включает:**
> - Установку металлического каркаса
> - Двухслойную обшивку ГКЛ с обеих сторон
> - Заделку швов с армированием
> - Грунтование
>
> Нашел также более простой вариант (однослойная обшивка, код 10-05-001-01) за 207,480 руб., если двухслойная не обязательна.

#### Реализация через MCP (Model Context Protocol)

##### MCP Server (Python)

```python
from mcp.server import Server
from mcp.types import Tool, TextContent
import sqlite3
import json

app = Server("estimates-search")

# Инициализация БД
db = sqlite3.connect('estimates.db')
db.row_factory = sqlite3.Row

@app.list_tools()
async def list_tools():
    """Регистрируем инструменты для Claude"""
    return [
        Tool(
            name="search_rates",
            description="""
            Поиск расценок по описанию работы.

            Args:
                query (str): Описание работы (например, "перегородки гипсокартон")
                unit_type (str, optional): Фильтр по единице измерения (м2, м3, шт)
                max_results (int, optional): Максимум результатов (default: 10)

            Returns:
                List[Dict]: Список найденных расценок с кодами и ценами
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "unit_type": {"type": "string"},
                    "max_results": {"type": "integer", "default": 10}
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="calculate_cost",
            description="""
            Рассчитывает стоимость работы для заданного объема.

            Args:
                rate_code (str): Код расценки (например, "10-05-001-01")
                quantity (float): Объем работ в единицах расценки

            Returns:
                Dict: Детальный расчет стоимости
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "rate_code": {"type": "string"},
                    "quantity": {"type": "number"}
                },
                "required": ["rate_code", "quantity"]
            }
        ),
        Tool(
            name="get_rate_details",
            description="""
            Получает детальную информацию о расценке.

            Args:
                rate_code (str): Код расценки
                include_resources (bool): Включить ресурсы (default: True)

            Returns:
                Dict: Полное описание расценки
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "rate_code": {"type": "string"},
                    "include_resources": {"type": "boolean", "default": True}
                },
                "required": ["rate_code"]
            }
        ),
        Tool(
            name="compare_rates",
            description="""
            Сравнивает несколько расценок между собой.

            Args:
                rate_codes (List[str]): Список кодов расценок для сравнения
                quantity (float): Объем для расчета

            Returns:
                Dict: Сравнительная таблица
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "rate_codes": {"type": "array", "items": {"type": "string"}},
                    "quantity": {"type": "number"}
                },
                "required": ["rate_codes", "quantity"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    """Обработка вызовов инструментов"""

    if name == "search_rates":
        query = arguments["query"]
        unit_type = arguments.get("unit_type")
        max_results = arguments.get("max_results", 10)

        # FTS5 поиск
        fts_query = ' '.join([f'{word}*' for word in query.split()])

        sql = """
            SELECT
                r.rate_code,
                r.rate_full_name,
                r.rate_short_name,
                r.unit_measure_full,
                r.unit_type,
                r.total_cost,
                r.unit_quantity,
                ROUND(r.total_cost / r.unit_quantity, 2) AS cost_per_unit,
                rates_fts.rank
            FROM rates r
            JOIN rates_fts ON rates_fts.rowid = r.id
            WHERE rates_fts MATCH ?
        """

        params = [fts_query]

        if unit_type:
            sql += " AND r.unit_type = ?"
            params.append(unit_type)

        sql += " ORDER BY rates_fts.rank LIMIT ?"
        params.append(max_results)

        cursor = db.execute(sql, params)
        results = [dict(row) for row in cursor.fetchall()]

        return [TextContent(
            type="text",
            text=json.dumps(results, ensure_ascii=False, indent=2)
        )]

    elif name == "calculate_cost":
        rate_code = arguments["rate_code"]
        quantity = arguments["quantity"]

        cursor = db.execute("""
            SELECT
                rate_code,
                rate_full_name,
                rate_short_name,
                unit_measure_full,
                unit_type,
                unit_quantity,
                total_cost,
                materials_cost,
                resources_cost,
                ROUND((total_cost / unit_quantity) * ?, 2) AS calculated_total,
                ROUND((materials_cost / unit_quantity) * ?, 2) AS calculated_materials,
                ROUND((resources_cost / unit_quantity) * ?, 2) AS calculated_resources,
                ROUND(total_cost / unit_quantity, 2) AS cost_per_unit
            FROM rates
            WHERE rate_code = ?
        """, (quantity, quantity, quantity, rate_code))

        result = cursor.fetchone()

        if not result:
            return [TextContent(type="text", text=json.dumps({"error": "Расценка не найдена"}))]

        return [TextContent(
            type="text",
            text=json.dumps(dict(result), ensure_ascii=False, indent=2)
        )]

    elif name == "get_rate_details":
        rate_code = arguments["rate_code"]
        include_resources = arguments.get("include_resources", True)

        # Основная информация
        cursor = db.execute("""
            SELECT
                rate_code,
                rate_full_name,
                rate_short_name,
                composition_text,
                unit_measure_full,
                total_cost,
                materials_cost,
                resources_cost
            FROM rates
            WHERE rate_code = ?
        """, (rate_code,))

        rate = dict(cursor.fetchone())

        # Добавляем ресурсы
        if include_resources:
            cursor = db.execute("""
                SELECT
                    resource_code,
                    resource_name,
                    quantity,
                    unit,
                    price_per_unit,
                    total_price
                FROM resources
                WHERE rate_code = ?
                ORDER BY total_price DESC
            """, (rate_code,))

            rate["resources"] = [dict(row) for row in cursor.fetchall()]

        return [TextContent(
            type="text",
            text=json.dumps(rate, ensure_ascii=False, indent=2)
        )]

    elif name == "compare_rates":
        rate_codes = arguments["rate_codes"]
        quantity = arguments["quantity"]

        placeholders = ','.join(['?' for _ in rate_codes])

        cursor = db.execute(f"""
            SELECT
                rate_code,
                rate_full_name,
                rate_short_name,
                unit_type,
                ROUND((total_cost / unit_quantity) * ?, 2) AS total_for_quantity,
                ROUND((materials_cost / unit_quantity) * ?, 2) AS materials_for_quantity,
                ROUND(total_cost / unit_quantity, 2) AS cost_per_unit
            FROM rates
            WHERE rate_code IN ({placeholders})
            ORDER BY total_for_quantity
        """, [quantity, quantity] + rate_codes)

        results = [dict(row) for row in cursor.fetchall()]

        return [TextContent(
            type="text",
            text=json.dumps(results, ensure_ascii=False, indent=2)
        )]

if __name__ == "__main__":
    app.run()
```

##### Claude Agent Configuration

```json
{
  "mcpServers": {
    "estimates-search": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "DB_PATH": "/path/to/estimates.db"
      }
    }
  }
}
```

##### Пример промпта для Claude Agent

```markdown
# System Prompt для Claude Agent

Ты - эксперт-сметчик с доступом к базе строительных расценок.

## Твои возможности:

1. **search_rates(query)** - поиск расценок по описанию работы
2. **calculate_cost(rate_code, quantity)** - точный расчет стоимости
3. **get_rate_details(rate_code)** - детальная информация
4. **compare_rates(rate_codes, quantity)** - сравнение вариантов

## Правила работы:

1. **Всегда** используй инструменты для получения данных из БД
2. **Не придумывай** цены или расценки - только реальные данные
3. **Проверяй единицы измерения** перед расчетом
4. Если находишь несколько вариантов - **предлагай выбор**
5. **Поясняй** откуда взялись цифры в расчетах
6. При неоднозначности - **задавай уточняющие вопросы**

## Формат ответа:

1. Краткий ответ на вопрос
2. Детальный расчет с пояснениями
3. Альтернативы (если есть)
4. Дополнительная информация (состав работ, ресурсы)

## Примеры обработки запросов:

### Запрос: "Сколько стоит 150 м² перегородок из гипсокартона?"

**Шаги:**
1. `search_rates("перегородки гипсокартон", unit_type="м2")`
2. Анализ результатов (могут быть варианты с 1 или 2 слоями)
3. Если несколько вариантов - спросить уточнение
4. `calculate_cost(выбранный_код, 150)`
5. Форматировать ответ с пояснениями

### Запрос: "Какая разница между 10-05-001-01 и 10-06-037-02?"

**Шаги:**
1. `get_rate_details("10-05-001-01")`
2. `get_rate_details("10-06-037-02")`
3. `compare_rates(["10-05-001-01", "10-06-037-02"], 100)`
4. Объяснить различия простым языком
```

#### Преимущества гибридного подхода

✅ **Естественный язык:**
- Пользователь пишет как хочет
- Claude понимает контекст
- Не нужно знать коды расценок

✅ **Интеллектуальный поиск:**
- Синонимы ("ГКЛ" = "гипсокартон")
- Опечатки
- Неполные запросы
- Контекстное уточнение

✅ **Лучший UX:**
- Диалоговый интерфейс
- Объяснения расчетов
- Альтернативы
- Советы

✅ **Гибкость:**
- Можно добавлять новые tools
- Claude адаптируется к изменениям
- Расширяемая архитектура

✅ **Надежность данных:**
- SQLite = структурированное хранение
- Claude не может "придумать" цены
- Все данные из БД

#### Дополнительные возможности

**1. Контекстная память (через проекты Claude)**

```python
# Claude запоминает предыдущие расчеты в рамках проекта
User: "Сколько стоит перегородки на 100 м²?"
Claude: [расчет]

User: "А если 150?"
Claude: [использует предыдущую найденную расценку]
```

**2. Сложные расчеты**

```python
User: "Сколько стоит отремонтировать офис 200м²: перегородки, потолки, стены?"
Claude:
- search_rates("перегородки")
- search_rates("потолки")
- search_rates("облицовка стен")
- Суммирует все позиции
- Выдает общий расчет
```

**3. Оптимизация выбора**

```python
User: "Что дешевле: перегородки из ГКЛ или из кирпича?"
Claude:
- search_rates("перегородки гипсокартон")
- search_rates("перегородки кирпич")
- compare_rates([коды], 100)
- Рекомендует с обоснованием
```

**4. Валидация запросов**

```python
User: "Сколько стоит 500 м³ перегородок?"
Claude: "Обратите внимание: перегородки обычно измеряются в м²,
         а не в м³. Возможно, вы имели в виду 500 м²?"
```

#### Стоимость Claude API

**Расчет стоимости для 1000 запросов:**

```
Модель: Claude 3.5 Sonnet
Input: 200K контекста (system prompt + tools) + 50 токенов запрос ≈ 250 токенов
Output: ~500 токенов ответ

Цена за 1M токенов:
- Input: $3
- Output: $15

Стоимость 1 запроса:
- Input: 0.25K * $3/1M = $0.00075
- Output: 0.5K * $15/1M = $0.0075
- Итого: ~$0.0082 за запрос

1000 запросов = ~$8.20
```

**Сравнение с альтернативами:**

| Решение | Стоимость 1000 запросов | Качество ответов |
|---------|------------------------|------------------|
| Только SQLite FTS | $0 | Список расценок без пояснений |
| Elasticsearch | ~$3 (инфраструктура) | Релевантный поиск |
| Claude + SQLite | ~$8 | Интеллектуальные ответы с расчетами |

#### Недостатки

⚠️ **Стоимость API:**
- Окупается при <10K запросов/месяц
- Для высокой нагрузки дорого

⚠️ **Зависимость от внешнего сервиса:**
- Нужен интернет
- Возможны задержки API
- Rate limits

⚠️ **Latency:**
- 1-3 секунды на ответ
- Vs <100ms для чистого SQL

#### Оптимизация стоимости

**1. Кэширование частых запросов:**

```python
import hashlib
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_search(query_hash):
    # Если запрос повторяется - отдаем из кэша
    pass
```

**2. Использование Claude Haiku для простых запросов:**

```python
# Простые запросы → Haiku ($0.25/$1.25 per 1M tokens)
# Сложные → Sonnet ($3/$15 per 1M tokens)

if is_simple_calculation(query):
    model = "claude-3-haiku"
else:
    model = "claude-3-sonnet"
```

**3. Батчинг запросов:**

```python
User: "Рассчитай 5 позиций"
Claude: [один вызов API для всех 5]
```

#### Когда использовать гибрид

✅ **Идеально для:**
- B2B SaaS с платными пользователями
- Internal tools для сметчиков
- Premium функция в freemium модели
- Пилотные проекты с инвесторами

✅ **Бизнес-модели:**
- Pay-per-query ($0.01-0.05 за расчет)
- Subscription ($50/месяц за 1000 запросов)
- Freemium (5 запросов бесплатно → платная подписка)

---

## 📊 Сравнительная таблица всех вариантов

| Критерий | SQLite FTS5 | PostgreSQL + pgvector | Elasticsearch | DuckDB | **ГИБРИД (SQLite + Claude)** |
|----------|-------------|----------------------|---------------|---------|------------------------------|
| **Сложность setup** | ⭐ Очень просто | ⭐⭐⭐ Средне | ⭐⭐⭐⭐⭐ Сложно | ⭐ Очень просто | ⭐⭐ Просто |
| **Стоимость инфраструктуры** | $0 | $10-50/мес | $95+/мес | $0 | $0 (только API) |
| **Стоимость запросов** | $0 | $0 | $0 | $0 | $0.008/запрос |
| **Качество поиска** | ⭐⭐⭐ Хорошо | ⭐⭐⭐⭐ Отлично | ⭐⭐⭐⭐⭐ Превосходно | ⭐⭐ Базовое | ⭐⭐⭐⭐⭐ Превосходно |
| **Скорость ответа** | <100ms | <200ms | <50ms | <500ms | 1-3s |
| **Масштабируемость** | До 1M | До 100M+ | До 1B+ | До 10M | До 100K/день |
| **Понимание контекста** | ❌ Нет | ⚠️ Частично | ⚠️ Частично | ❌ Нет | ✅ Да |
| **Естественный язык** | ❌ Нет | ❌ Нет | ❌ Нет | ❌ Нет | ✅ Да |
| **Объяснения расчетов** | ❌ Нет | ❌ Нет | ❌ Нет | ❌ Нет | ✅ Да |
| **Offline работа** | ✅ Да | ✅ Да | ✅ Да | ✅ Да | ❌ Нет |
| **Требования RAM** | <100MB | 4GB+ | 8GB+ | <500MB | <100MB |
| **Требования Disk** | 50-100MB | 1GB+ | 3GB+ | 0 (in-memory) | 50-100MB |
| **DevOps нагрузка** | ⭐ Минимальная | ⭐⭐⭐ Средняя | ⭐⭐⭐⭐⭐ Высокая | ⭐ Минимальная | ⭐⭐ Низкая |
| **Аналитические запросы** | ⭐⭐⭐ Хорошо (SQL) | ⭐⭐⭐⭐ Отлично | ⭐⭐⭐⭐⭐ Превосходно | ⭐⭐⭐⭐⭐ Превосходно | ⭐⭐⭐⭐ Отлично |
| **Подходит для MVP** | ✅ Да | ⚠️ Избыточно | ❌ Нет | ✅ Да | ✅ Да |
| **Подходит для Enterprise** | ⚠️ Ограниченно | ✅ Да | ✅ Да | ❌ Нет | ✅ Да |

### Легенда:
- ⭐ = уровень сложности/качества (больше звезд = выше)
- ✅ = подходит
- ⚠️ = с ограничениями
- ❌ = не подходит

---

## 🎯 Рекомендации по выбору

### Для стартапа / MVP (бюджет <$1000/мес):

**ГИБРИД (SQLite + Claude API)** - если:
- Нужен wow-эффект для инвесторов
- <5000 запросов/месяц
- Важен UX

**SQLite FTS5** - если:
- Нужно быстро запустить
- Бюджет = $0
- Технический пользователь (знает как формулировать запросы)

### Для среднего бизнеса (бюджет $1000-10000/мес):

**PostgreSQL + pgvector** - если:
- 10K-100K запросов/день
- Нужна высокая точность поиска
- Есть DevOps команда

**ГИБРИД + Кэширование** - если:
- Много повторяющихся запросов
- Премиум сегмент (B2B)
- Ценность точности > стоимости

### Для enterprise (бюджет >$10000/мес):

**Elasticsearch** - если:
- >100K запросов/день
- Нужна real-time аналитика
- Сложные faceted searches
- Уже используется Elastic Stack

**ГИБРИД на базе PostgreSQL** - если:
- Критична точность
- Высокая ценность каждого запроса
- Комбинация структурированных данных + NL запросов

### Для аналитики / исследований:

**DuckDB** - идеально для:
- Ad-hoc анализа
- Jupyter notebooks
- Data science
- Не production

---

## 🚀 План внедрения ГИБРИДА (рекомендуемый)

### Фаза 1: MVP (1-2 недели)

**Цель:** Доказать концепцию

1. ✅ Создать SQLite БД с FTS5
2. ✅ ETL скрипт для загрузки Excel
3. ✅ Базовый MCP сервер (4 инструмента)
4. ✅ Интеграция с Claude API
5. ✅ Тестирование на 10 типовых запросах

**Метрики успеха:**
- Точность поиска >90%
- Время ответа <3s
- Стоимость <$0.01/запрос

### Фаза 2: Оптимизация (2-3 недели)

6. ✅ Кэширование частых запросов (Redis)
7. ✅ A/B тестирование промптов
8. ✅ Добавление аналитики (логирование запросов)
9. ✅ Оптимизация стоимости (Haiku для простых запросов)
10. ✅ UI/UX для конечных пользователей

**Метрики:**
- Снижение стоимости на 30-50%
- Hit rate кэша >60%

### Фаза 3: Масштабирование (1-2 месяца)

11. ✅ Мониторинг и алерты
12. ✅ Автоматическое обновление БД
13. ✅ Multi-tenant архитектура
14. ✅ API для внешних интеграций
15. ✅ Документация и SDK

### Фаза 4: Advanced features

16. ✅ Сравнение региональных цен
17. ✅ Прогнозирование стоимости
18. ✅ Интеграция с BIM моделями
19. ✅ Экспорт в сметные программы
20. ✅ Голосовой интерфейс

---

## 💡 Дополнительные идеи для ГИБРИДА

### 1. Мультимодальность

```python
# Пользователь загружает чертеж
User: [прикладывает PDF чертеж]
"Сколько будет стоить построить это?"

Claude:
1. Анализирует чертеж (Vision API)
2. Извлекает объемы работ
3. Подбирает расценки для каждой позиции
4. Формирует полную смету
```

### 2. Интеграция с CAD/BIM

```python
# Экспорт из Revit/ArchiCAD
User: [выгрузка IFC файла]

Claude:
1. Парсит IFC
2. Извлекает спецификацию работ
3. Автоматически находит расценки
4. Создает смету
```

### 3. Ассистент сметчика

```python
User: "Проверь мою смету на ошибки"
[прикладывает Excel]

Claude:
1. Анализирует позиции
2. Сравнивает с БД расценок
3. Находит несоответствия
4. Предлагает корректировки
```

### 4. Региональные коэффициенты

```python
# Расширяем БД региональными данными
User: "Сколько стоит в Москве vs Екатеринбург?"

Claude:
- Применяет региональные коэффициенты
- Учитывает транспортные расходы
- Показывает разницу
```

---

## 📝 Выводы и финальная рекомендация

### ⭐ Для вашего кейса рекомендую:

**ГИБРИД: SQLite FTS5 + Claude API Agent**

**Обоснование:**

1. **Оптимальный баланс:** Простота SQLite + интеллект Claude
2. **Быстрый старт:** 1-2 недели до MVP
3. **Низкий risk:** Можно начать без Claude, добавить потом
4. **Масштабируемость:** Легко мигрировать на PostgreSQL при росте
5. **Wow-эффект:** "Википедия расценок" с естественным языком
6. **Экономика:** Окупается уже при 100 запросах/день по $0.10

### Этапы внедрения:

**Week 1:** SQLite + ETL + базовый поиск
**Week 2:** MCP сервер + интеграция Claude
**Week 3:** Тестирование + оптимизация промптов
**Week 4:** UI + запуск пилота

### Следующие шаги:

1. Создать SQLite БД из вашего Excel файла
2. Реализовать 4 базовых MCP tool
3. Протестировать на 20 реальных запросах
4. Измерить точность и стоимость
5. Принять решение о дальнейшем развитии

---

**Вопросы для обсуждения:**

1. Какой ожидаемый объем запросов в день?
2. Кто целевые пользователи (сметчики, менеджеры, клиенты)?
3. Критична ли offline работа?
4. Есть ли бюджет на API ($50-500/мес)?
5. Планируется ли интеграция с другими системами (BIM, ERP)?

На основе ответов можем скорректировать рекомендацию.
