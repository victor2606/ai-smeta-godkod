# Строительный Сметный Поиск - База Знаний Проекта

## О проекте

Это система управления строительными расценками с полнотекстовым поиском на русском языке. Проект предоставляет API для поиска, расчета стоимости и сравнения строительных расценок из базы данных ГЭСН/ФЕР.

**База данных:** 28,686 расценок, 294,883 ресурсов
**Размер БД:** ~290 MB (SQLite с FTS5)
**Язык:** Python 3.x

---

## Структура директорий

```
n8npiplines-bim/
├── src/
│   ├── database/              # Управление БД и схемой
│   │   ├── db_manager.py      # DatabaseManager - работа с SQLite
│   │   ├── schema.sql         # SQL схема (rates, resources, FTS5)
│   │   └── fts_config.py      # Конфигурация полнотекстового поиска
│   │
│   ├── search/                # Основные поисковые модули
│   │   ├── search_engine.py   # SearchEngine - FTS5 поиск расценок
│   │   ├── cost_calculator.py # CostCalculator - расчет стоимости
│   │   └── rate_comparator.py # RateComparator - сравнение расценок
│   │
│   ├── etl/                   # Извлечение и загрузка данных
│   │   ├── data_aggregator.py # Агрегация данных из Excel
│   │   └── db_populator.py    # Заполнение БД
│   │
│   └── utils/                 # Вспомогательные модули
│       └── agent_helpers.py   # Helper функции для AI-агента
│
├── data/
│   ├── raw/                   # Исходные Excel файлы
│   ├── processed/             # Готовые БД
│   │   └── estimates.db       # Основная SQLite БД
│   └── cache/                 # Кэш запросов
│       └── query_cache.json   # JSON-кэш (TTL: 24 часа)
│
├── agents/
│   └── estimates_agent_prompt.md  # Промпт для Claude Code Agent
│
├── docs/
│   ├── estimates_search_architecture.md  # Архитектура системы
│   └── tasks/                 # Управление задачами
│       ├── active-tasks.md    # Активные задачи
│       └── archive/           # Архив завершенных задач
│
├── scripts/
│   └── build_database.py      # Скрипт сборки БД из Excel
│
└── tests/                     # Unit и интеграционные тесты
```

---

## Схема базы данных

### Основные таблицы

#### 1. `rates` (Расценки)
Главная таблица с информацией о расценках:

```sql
CREATE TABLE rates (
    rate_code TEXT PRIMARY KEY,        -- Код расценки (например, "ГЭСНп81-01-001-01")
    rate_full_name TEXT NOT NULL,      -- Полное название
    rate_short_name TEXT,              -- Краткое название
    unit_quantity NUMERIC DEFAULT 1,   -- Кол-во единиц (100, 1, 1000)
    unit_type TEXT NOT NULL,           -- Единица измерения (м3, м2, т, шт)
    total_cost NUMERIC DEFAULT 0,      -- Общая стоимость
    materials_cost NUMERIC DEFAULT 0,  -- Стоимость материалов
    resources_cost NUMERIC DEFAULT 0,  -- Стоимость работы + техника

    -- ГЭСН/ФЕР иерархия (13 полей):
    category_type TEXT,                -- Уровень 1: Категория
    collection_code TEXT,              -- Уровень 2: Сборник (код)
    collection_name TEXT,              -- Уровень 2: Сборник (название)
    department_code TEXT,              -- Уровень 3: Отдел (код)
    department_name TEXT,              -- Уровень 3: Отдел (название)
    department_type TEXT,              -- Уровень 3: Отдел (тип)
    section_code TEXT,                 -- Уровень 4: Раздел (код)
    section_name TEXT,                 -- Уровень 4: Раздел (название)
    section_type TEXT,                 -- Уровень 4: Раздел (тип)
    subsection_code TEXT,              -- Уровень 5: Подраздел (код)
    subsection_name TEXT,              -- Уровень 5: Подраздел (название)
    table_code TEXT,                   -- Уровень 6: Таблица (код)
    table_name TEXT,                   -- Уровень 6: Таблица (название)

    search_text TEXT,                  -- Конкатенация для FTS5
    composition TEXT,                  -- JSON с составом работ
    overhead_rate REAL DEFAULT 0,      -- НР (Накладные расходы)
    profit_margin REAL DEFAULT 0,      -- СП (Сметная прибыль)

    created_at TEXT,
    updated_at TEXT
);
```

**Индексы:**
- PRIMARY KEY на `rate_code`
- Индексы на `unit_type`, `category`, `costs`
- Иерархические индексы: `collection`, `department`, `section`, `subsection`, `table`
- Композитный индекс `idx_rates_hierarchy_full` для навигации

#### 2. `rates_fts` (Полнотекстовый поиск)
FTS5 виртуальная таблица для поиска:

```sql
CREATE VIRTUAL TABLE rates_fts USING fts5(
    rate_code,
    rate_full_name,
    rate_short_name,
    category,
    search_text,
    tokenize='unicode61 remove_diacritics 2',
    content='rates',
    content_rowid='rowid'
);
```

**Триггеры:** Автоматическая синхронизация при INSERT/UPDATE/DELETE в `rates`

#### 3. `resources` (Ресурсы)
Детализация по материалам, работе, технике:

```sql
CREATE TABLE resources (
    resource_id INTEGER PRIMARY KEY AUTOINCREMENT,
    rate_code TEXT NOT NULL,           -- FK к rates
    resource_code TEXT NOT NULL,       -- Код ресурса
    resource_type TEXT NOT NULL,       -- Тип (Материал, Ресурс, Состав работ)
    resource_name TEXT NOT NULL,       -- Название
    quantity NUMERIC DEFAULT 0,        -- Количество
    unit TEXT NOT NULL,                -- Единица измерения
    unit_cost NUMERIC DEFAULT 0,       -- Цена за единицу
    total_cost NUMERIC DEFAULT 0,      -- Итого (quantity * unit_cost)

    -- P1 расширения (machinery/labor):
    machinist_wage REAL DEFAULT 0,
    machinist_labor_hours REAL DEFAULT 0,
    machinist_machine_hours REAL DEFAULT 0,
    cost_without_wages REAL DEFAULT 0,
    relocation_included INTEGER DEFAULT 0,
    personnel_code TEXT,
    machinist_grade INTEGER,

    FOREIGN KEY (rate_code) REFERENCES rates(rate_code) ON DELETE CASCADE
);
```

#### 4. `resource_price_statistics` (Статистика цен)
Статистика по ценам ресурсов:

```sql
CREATE TABLE resource_price_statistics (
    price_stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_code TEXT NOT NULL,
    rate_code TEXT NOT NULL,
    current_price_min REAL,
    current_price_max REAL,
    current_price_mean REAL,
    current_price_median REAL,
    unit_match INTEGER DEFAULT 0,
    material_resource_cost REAL,
    total_resource_cost REAL,

    UNIQUE(resource_code, rate_code)
);
```

#### 5. Опциональные таблицы (P2)
- `resource_mass` - масса ресурсов (3 поля)
- `services` - услуги (6 полей)

---

## Основные модули

### 1. SearchEngine (`src/search/search_engine.py`)

**Назначение:** Полнотекстовый поиск расценок на русском языке с использованием SQLite FTS5.

**Класс:** `SearchEngine(db_manager: DatabaseManager)`

**Методы:**

#### `search(query: str, filters: Dict = None, limit: int = 100) -> List[Dict]`
Полнотекстовый поиск по описанию работ.

**Параметры:**
- `query` (str) - русский текст запроса (например, "бетон монолитный")
- `filters` (dict, optional) - фильтры:
  - `unit_type` (str) - единица измерения ("м3", "м2", "т")
  - `min_cost` (float) - минимальная стоимость
  - `max_cost` (float) - максимальная стоимость
  - `category` (str) - код категории
- `limit` (int) - макс. кол-во результатов (default: 100, max: 1000)

**Возвращает:** `List[Dict]` с полями:
```python
{
    'rate_code': 'ГЭСНп10-05-001-01',
    'rate_full_name': 'Устройство перегородок...',
    'rate_short_name': 'Перегородки ГКЛ',
    'unit_measure_full': '100 м2',
    'cost_per_unit': 1383.20,
    'total_cost': 138320.26,
    'rank': -2.345  # FTS5 score (ближе к 0 = лучше)
}
```

**Пример:**
```python
from src.database.db_manager import DatabaseManager
from src.search.search_engine import SearchEngine

db = DatabaseManager('data/processed/estimates.db')
search_engine = SearchEngine(db)

# Простой поиск
results = search_engine.search("перегородки гипсокартон")

# С фильтрами
results = search_engine.search(
    "бетон монолитный",
    filters={'unit_type': 'м3', 'min_cost': 1000, 'max_cost': 50000},
    limit=50
)
```

#### `search_by_code(rate_code: str) -> List[Dict]`
Поиск по коду расценки (с поддержкой префиксов).

**Параметры:**
- `rate_code` (str) - код или префикс кода (например, "ГЭСНп81-01")

**Пример:**
```python
# Найти все расценки, начинающиеся с "ГЭСНп81-01"
results = search_engine.search_by_code("ГЭСНп81-01")

# Найти конкретную расценку
result = search_engine.search_by_code("ГЭСНп81-01-001-01")
```

---

### 2. CostCalculator (`src/search/cost_calculator.py`)

**Назначение:** Расчет точной стоимости для заданного объема работ с детализацией по ресурсам.

**Класс:** `CostCalculator(db_manager: DatabaseManager)`

**Методы:**

#### `calculate(rate_code: str, quantity: float) -> Dict`
Рассчитать стоимость для заданного количества.

**Параметры:**
- `rate_code` (str) - код расценки
- `quantity` (float) - объем работ (>0, в тех же единицах, что и расценка)

**Возвращает:** `Dict`:
```python
{
    'rate_info': {
        'rate_code': 'ГЭСНп10-05-001-01',
        'rate_full_name': 'Устройство перегородок...',
        'unit_type': 'м2'
    },
    'base_cost': 138320.26,           # Стоимость из БД
    'cost_per_unit': 1383.20,         # За 1 единицу
    'calculated_total': 207480.27,    # Итого для quantity
    'materials': 156341.85,           # Материалы
    'resources': 51138.42,            # Работа + техника
    'quantity': 150
}
```

**ВАЖНО:**
- Расценка может быть на 100 м2, а пользователь запрашивает 150 м2
- `calculate()` сам пересчитает: `(138320.26 / 100) * 150 = 207480.27`
- Всегда передавайте реальный объем, не делите вручную!

**Пример:**
```python
calculator = CostCalculator(db)

# Расценка на 100 м2, расчет для 150 м2
result = calculator.calculate("ГЭСНп10-05-001-01", 150)
print(f"Стоимость: {result['calculated_total']} руб.")
```

#### `get_detailed_breakdown(rate_code: str, quantity: float) -> Dict`
Получить детальную разбивку с ресурсами.

**Возвращает:** Все поля из `calculate()` + `breakdown`:
```python
{
    # ... все поля из calculate()
    'breakdown': [
        {
            'resource_code': 'ГЭСН101-1714',
            'resource_name': 'Листы гипсокартонные ГКЛ 12.5 мм',
            'resource_type': 'Материал',
            'original_quantity': 202.0,     # Из БД
            'adjusted_quantity': 303.0,     # Пересчитано для quantity
            'unit': 'м2',
            'unit_cost': 245.50,
            'adjusted_cost': 74386.50
        },
        # ... остальные ресурсы
    ]
}
```

**Пример:**
```python
breakdown = calculator.get_detailed_breakdown("ГЭСНп10-05-001-01", 150)

# Вывести все материалы
materials = [r for r in breakdown['breakdown'] if 'Материал' in r['resource_type']]
for m in materials:
    print(f"{m['resource_name']}: {m['adjusted_quantity']} {m['unit']}")
```

---

### 3. RateComparator (`src/search/rate_comparator.py`)

**Назначение:** Сравнение нескольких расценок между собой и поиск альтернатив.

**Класс:** `RateComparator(db_path: str = 'data/processed/estimates.db')`

**Методы:**

#### `compare(rate_codes: List[str], quantity: float) -> pd.DataFrame`
Сравнить список расценок.

**Параметры:**
- `rate_codes` (List[str]) - коды расценок для сравнения
- `quantity` (float) - объем работ для расчета (>0)

**Возвращает:** `pd.DataFrame` с колонками:
- `rate_code` - код расценки
- `rate_full_name` - название
- `unit_type` - единица измерения
- `cost_per_unit` - стоимость за единицу
- `total_for_quantity` - общая стоимость для quantity
- `materials_for_quantity` - материалы для quantity
- `difference_from_cheapest` - разница с минимумом (руб.)
- `difference_percent` - разница с минимумом (%)

**Сортировка:** По `total_for_quantity` (от дешевого к дорогому)

**Пример:**
```python
comparator = RateComparator('data/processed/estimates.db')

df = comparator.compare(
    ['ГЭСНп10-05-001-01', 'ГЭСНп10-06-037-02'],
    quantity=100
)

print(df[['rate_code', 'total_for_quantity', 'difference_percent']])
```

#### `find_alternatives(rate_code: str, max_results: int = 5) -> pd.DataFrame`
Найти похожие расценки через FTS5.

**Параметры:**
- `rate_code` (str) - исходная расценка
- `max_results` (int) - макс. кол-во альтернатив (default: 5)

**Возвращает:** `pd.DataFrame` с той же структурой, что `compare()`
Первая строка - исходная расценка (для сравнения)

**Пример:**
```python
alternatives = comparator.find_alternatives("ГЭСНп10-05-001-01", max_results=5)

# Показать только альтернативы (без исходной)
alternatives_only = alternatives.iloc[1:]
print(alternatives_only[['rate_code', 'rate_full_name', 'difference_percent']])
```

---

### 4. AgentHelpers (`src/utils/agent_helpers.py`)

**Назначение:** Обертки над основными модулями с Rich-форматированием для AI-агента.

**Функции:**

#### `natural_search(query, filters=None, limit=10, db_path='...')`
Поиск с красивым форматированием.

**Возвращает:**
```python
{
    'results': [...],           # Список результатов
    'formatted_text': str,      # Rich таблица (готовая к выводу)
    'query_info': {
        'query': str,
        'result_count': int
    }
}
```

#### `quick_calculate(rate_code_or_description, quantity, db_path='...')`
Умный расчет: автоматически определяет код или описание.

```python
# Если передан код - использует его
result = quick_calculate("ГЭСНп10-05-001-01", 150)

# Если передано описание - сначала ищет, потом считает
result = quick_calculate("бетон монолитный B25", 50)
```

**Возвращает:**
```python
{
    'calculation': {...},       # Результат расчета
    'formatted_text': str,      # Rich панель с расчетом
    'rate_used': str,           # Код расценки
    'search_performed': bool    # Был ли выполнен поиск
}
```

#### `show_rate_details(rate_code, db_path='...')`
Подробная информация о расценке с таблицей ресурсов.

#### `compare_variants(descriptions: List[str], quantity, db_path='...')`
Сравнение вариантов по описаниям (автопоиск).

#### `find_similar_rates(rate_code, max_results=5, db_path='...')`
Поиск похожих расценок с рекомендациями.

**Особенности:**
- Все функции возвращают `formatted_text` - готовый Rich-форматированный вывод
- Автоматический кэш запросов (TTL: 24 часа, `data/cache/query_cache.json`)
- Обработка ошибок с понятными сообщениями

---

## Зависимости между модулями

```
┌─────────────────────────────────────────────────────┐
│                 agent_helpers.py                    │
│            (High-level API для агента)              │
└─────────────────┬───────────────────────────────────┘
                  │
                  ├──► SearchEngine ────┐
                  ├──► CostCalculator ──┤
                  └──► RateComparator ──┤
                                        │
                                        ▼
                                 DatabaseManager
                                        │
                                        ▼
                                 estimates.db
                                 (SQLite + FTS5)
```

**Иерархия импортов:**
1. **Уровень 1:** `db_manager.py` - базовый менеджер БД
2. **Уровень 2:** `search_engine.py`, `cost_calculator.py`, `rate_comparator.py` - основные модули
3. **Уровень 3:** `agent_helpers.py` - обертки для AI-агента

**Правило:** Никогда не импортируйте напрямую из `agent_helpers.py` в тестах основных модулей.

---

## Типовые сценарии работы

### Сценарий 1: Поиск и расчет стоимости

```python
from src.database.db_manager import DatabaseManager
from src.search.search_engine import SearchEngine
from src.search.cost_calculator import CostCalculator

# 1. Открыть БД
db = DatabaseManager('data/processed/estimates.db')

# 2. Найти расценку
search_engine = SearchEngine(db)
results = search_engine.search("перегородки гипсокартон один слой")

if results:
    rate_code = results[0]['rate_code']

    # 3. Рассчитать стоимость
    calculator = CostCalculator(db)
    cost = calculator.calculate(rate_code, 150)

    print(f"Стоимость: {cost['calculated_total']} руб.")
    print(f"Материалы: {cost['materials']} руб.")
    print(f"Работа: {cost['resources']} руб.")
```

### Сценарий 2: Сравнение вариантов

```python
from src.search.search_engine import SearchEngine
from src.search.rate_comparator import RateComparator

# 1. Найти расценки по описанию
search = SearchEngine(db)
single_layer = search.search("перегородки гипсокартон один слой")[0]
double_layer = search.search("перегородки гипсокартон два слоя")[0]

# 2. Сравнить
comparator = RateComparator('data/processed/estimates.db')
df = comparator.compare(
    [single_layer['rate_code'], double_layer['rate_code']],
    quantity=100
)

# 3. Показать результат
for idx, row in df.iterrows():
    print(f"{row['rate_full_name']}: {row['total_for_quantity']} руб. "
          f"(+{row['difference_percent']}%)")
```

### Сценарий 3: Детальная разбивка

```python
calculator = CostCalculator(db)
breakdown = calculator.get_detailed_breakdown("ГЭСНп10-05-001-01", 100)

# Группировка по типам
materials = [r for r in breakdown['breakdown'] if 'Материал' in r['resource_type']]
labor = [r for r in breakdown['breakdown'] if 'Работа' in r['resource_type']]

print(f"Материалы ({len(materials)} позиций):")
for m in materials:
    print(f"  {m['resource_name']}: {m['adjusted_quantity']} {m['unit']} "
          f"x {m['unit_cost']} = {m['adjusted_cost']} руб.")
```

---

## Инструкции по запуску

### Первоначальная настройка

**1. Проверить наличие БД:**
```bash
ls -lh data/processed/estimates.db
# Должно быть ~290 MB
```

**2. Если БД нет - собрать из Excel:**
```bash
python scripts/build_database.py
```

Процесс сборки:
1. Читает Excel файлы из `data/raw/`
2. Агрегирует данные через `DataAggregator`
3. Заполняет БД через `DatabasePopulator`
4. Создает FTS5 индексы
5. Сохраняет в `data/processed/estimates.db`

**Время выполнения:** ~5-10 минут
**Требования:** pandas, openpyxl, sqlite3

### Работа через агента

**1. Запустить Claude Code Agent:**
```bash
claude-code
```

**2. При первом запросе агент должен:**
- Проверить `data/processed/estimates.db`
- Если БД нет - предложить запустить `build_database.py`
- После проверки БД - готов к работе

**3. Примеры запросов:**

```
Пользователь: Сколько будет стоить 150 м² перегородок из ГКЛ?

Агент:
1. search_engine.search("перегородки гипсокартон")
2. calculator.calculate(найденный_код, 150)
3. Вывод результата с детализацией
```

```
Пользователь: Сравни однослойные и двухслойные перегородки

Агент:
1. search_engine.search("перегородки однослойные")
2. search_engine.search("перегородки двухслойные")
3. comparator.compare([код1, код2], quantity)
4. Вывод таблицы сравнения
```

---

## Примеры запросов и ожидаемых ответов

### Пример 1: Простой расчет

**Запрос:**
"Сколько стоит устройство 150 м² перегородок из ГКЛ в один слой?"

**Ожидаемый ответ:**
```
Стоимость устройства 150 м² перегородок из ГКЛ в один слой составит **207,480.27 руб.**

## Детальный расчет

**Расценка:** ГЭСНп10-05-001-01
**Название:** Устройство перегородок из гипсокартонных листов в один слой на металлическом каркасе
**Объём работ:** 150 м²

**ИТОГО: 207,480.27 руб.**

Из них:
- Материалы: 156,341.85 руб. (75.3%)
- Работа + техника: 51,138.42 руб. (24.7%)

**Как рассчитано:**
- Базовая стоимость расценки: 138,320.26 руб. (на 100 м²)
- Стоимость за 1 м²: 1,383.20 руб.
- Для 150 м²: 1,383.20 × 150 = **207,480.27 руб.**
```

### Пример 2: Сравнение

**Запрос:**
"Сравни однослойные и двухслойные перегородки для 100 м²"

**Ожидаемый ответ:**
```
## Сравнение расценок на перегородки

Для объёма **100 м²**:

| Тип перегородки | Код расценки | Стоимость | Разница |
|-----------------|--------------|-----------|---------|
| **Однослойные** | ГЭСНп10-05-001-01 | 138,320.26 руб. | — |
| **Двухслойные** | ГЭСНп10-06-037-02 | 185,760.35 руб. | +47,440.09 руб. (+34.3%) |

### Выводы:

✅ **Однослойные** - дешевле на 34.3%
- Толщина: 12.5 мм
- Подходит для: внутренних ненагруженных перегородок

✅ **Двухслойные** - дороже, но прочнее
- Толщина: 25 мм
- Преимущества: лучшая звукоизоляция, выше прочность
```

### Пример 3: Поиск альтернатив

**Запрос:**
"Найди более дешёвый вариант для ГЭСНп10-05-001-01"

**Ожидаемый ответ:**
```
## Альтернативные расценки

Исходная расценка: ГЭСНп10-05-001-01 (138,320.26 руб.)

Найдены похожие расценки:

| Код | Название | Стоимость | Разница |
|-----|----------|-----------|---------|
| ГЭСНп10-05-002-01 | Перегородки облегченные | 125,450.18 руб. | **-9.3%** ⭐ |
| ГЭСНп10-05-003-01 | Перегородки стандарт | 138,320.26 руб. | 0% |
| ГЭСНп10-06-037-02 | Перегородки усиленные | 185,760.35 руб. | +34.3% |

⭐ Рекомендация: ГЭСНп10-05-002-01 дешевле на 12,870.08 руб. (9.3%)
```

---

## Проверка при первом запросе

**Чеклист для агента:**

1. **Проверить наличие БД:**
```python
import os
db_exists = os.path.exists('data/processed/estimates.db')
if not db_exists:
    print("⚠️ База данных не найдена!")
    print("Запустите: python scripts/build_database.py")
    exit()
```

2. **Проверить размер БД:**
```python
db_size = os.path.getsize('data/processed/estimates.db')
if db_size < 100_000_000:  # < 100 MB
    print("⚠️ База данных слишком маленькая, возможно повреждена")
```

3. **Проверить доступность модулей:**
```python
try:
    from src.search.search_engine import SearchEngine
    from src.search.cost_calculator import CostCalculator
    from src.search.rate_comparator import RateComparator
    print("✅ Все модули доступны")
except ImportError as e:
    print(f"❌ Ошибка импорта: {e}")
```

4. **Тестовый запрос:**
```python
from src.database.db_manager import DatabaseManager
from src.search.search_engine import SearchEngine

db = DatabaseManager('data/processed/estimates.db')
search = SearchEngine(db)
results = search.search("бетон", limit=1)

if results:
    print(f"✅ БД работает: найдена расценка {results[0]['rate_code']}")
else:
    print("⚠️ БД пустая или поиск не работает")
```

---

## Важные особенности

### 1. Единицы измерения

**Проблема:** Расценки хранятся с разными unit_quantity:
- Расценка A: `unit_quantity=100, unit_type='м2'` → "на 100 м2"
- Расценка B: `unit_quantity=1, unit_type='м3'` → "на 1 м3"

**Решение:** `CostCalculator` автоматически пересчитывает:
```python
# Пользователь запрашивает 150 м2
# Расценка в БД: unit_quantity=100, total_cost=138320.26
calculator.calculate(rate_code, 150)
# Внутри: (138320.26 / 100) * 150 = 207480.27
```

**Правило:** Всегда передавайте реальный объем в `calculate()`, не делите вручную!

### 2. Кэширование

`agent_helpers.py` использует JSON-кэш:
- Путь: `data/cache/query_cache.json`
- TTL: 24 часа
- Ключ: `f"search:{query}:{filters}:{limit}"`

**Очистка кэша:**
```bash
rm data/cache/query_cache.json
```

### 3. FTS5 Query Syntax

Поддерживаемые операторы:
- `бетон монолитный` - оба слова
- `"монтаж конструкций"` - точная фраза
- `бетон OR железобетон` - логическое ИЛИ
- `бетон NOT монтаж` - исключение
- `rate_full_name: земляные` - поиск в конкретном поле

### 4. Иерархическая навигация

Примеры запросов через иерархию:
```sql
-- Все расценки из сборника ГЭСНп81
SELECT * FROM rates WHERE collection_code = 'ГЭСНп81';

-- Drill-down по уровням
SELECT
    collection_name,
    department_name,
    section_name,
    COUNT(*) as rate_count
FROM rates
WHERE collection_code = 'ГЭСНп81'
GROUP BY collection_name, department_name, section_name;
```

---

## Архитектура системы

Подробная архитектура описана в `docs/estimates_search_architecture.md`

**Основные принципы:**

1. **Separation of Concerns:**
   - `database/` - работа с БД
   - `search/` - бизнес-логика поиска/расчетов
   - `utils/` - вспомогательные функции
   - `etl/` - загрузка данных

2. **Single Responsibility:**
   - `SearchEngine` - только поиск
   - `CostCalculator` - только расчеты
   - `RateComparator` - только сравнение

3. **Dependency Injection:**
   - Все модули принимают `DatabaseManager` в конструкторе
   - Легко тестировать с mock БД

4. **Error Handling:**
   - Все функции проверяют входные данные
   - `ValueError` для некорректных параметров
   - `sqlite3.Error` для ошибок БД
   - Понятные сообщения об ошибках

---

## Для Claude Code Agent

**Ты - эксперт-сметчик** с доступом к этим модулям. При работе:

1. **Всегда используй модули** - не придумывай цифры
2. **Проверяй единицы измерения** - критично для корректности
3. **Пояснения обязательны** - покажи откуда взялись цифры
4. **Структурируй ответ** - краткий ответ → детали → альтернативы
5. **Используй форматирование** - таблицы, списки, выделения
6. **При неоднозначности - спрашивай** - лучше уточнить
7. **Предлагай альтернативы** - покажи варианты дешевле/дороже

**Инструкции для агента:** См. `agents/estimates_agent_prompt.md` (620 строк с примерами)

---

## Тестирование

**Запуск тестов:**
```bash
pytest tests/
```

**Структура тестов:**
- `tests/test_search_engine.py` - SearchEngine
- `tests/test_cost_calculator.py` - CostCalculator
- `tests/test_rate_comparator.py` - RateComparator
- `tests/test_integration.py` - интеграционные тесты

**Coverage:**
```bash
pytest --cov=src tests/
```

---

## Состояние проекта

**Завершенные задачи:**
- ✅ Базовая схема БД (rates, resources, FTS5)
- ✅ SearchEngine с FTS5
- ✅ CostCalculator с детализацией
- ✅ RateComparator с альтернативами
- ✅ AgentHelpers с Rich форматированием
- ✅ ГЭСН/ФЕР иерархия (13 полей)
- ✅ P1 расширения (overhead, profit, machinery)
- ✅ P2 опциональные таблицы (resource_mass, services)

**Активные задачи:**
- 🟡 Задача 4.3: Интеграция Claude Code Agent (текущая)
- ⏳ Задачи 5.x: Тестирование
- ⏳ Задачи 6.x: Документация

См. `docs/tasks/active-tasks.md`

---

## Контакты и поддержка

**Репозиторий:** [внутренний проект]
**Документация:** `docs/`
**Промпт агента:** `agents/estimates_agent_prompt.md`
**Архитектура:** `docs/estimates_search_architecture.md`

**При проблемах:**
1. Проверить `data/processed/estimates.db` (должно быть ~290 MB)
2. Запустить `python scripts/build_database.py` при необходимости
3. Проверить логи в консоли (logging.INFO)
4. Запустить `pytest tests/` для проверки модулей
