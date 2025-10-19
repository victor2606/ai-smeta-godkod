# 🏗️ Система поиска расценок в сметной документации

Интеллектуальная система для быстрого поиска и расчета стоимости строительных работ на основе естественноязыковых запросов.

## 📋 Описание

Проект реализует гибридную архитектуру **SQLite FTS5 + Claude Code Agent** для работы с базой сметных расценок (740,000 строк, 73 колонки). Система позволяет находить расценки по описанию работ, рассчитывать стоимость для заданных объемов и получать детальную информацию о составе работ и ресурсах.

### Основные возможности

- **Полнотекстовый поиск** расценок с поддержкой морфологии
- **Автоматический расчет** стоимости для произвольных объемов работ
- **Детализация** по ресурсам (материалы, труд, техника)
- **Естественноязыковые запросы** через Claude Code (опционально)
- **Высокая производительность** (<100ms для поиска)

## 🏛️ Архитектура

```
Excel (740K строк)
    │
    ├─ ETL Pipeline (Python)
    │   ├─ Чтение и валидация данных
    │   ├─ Агрегация расценок
    │   └─ Извлечение единиц измерения
    │
    ↓
SQLite Database
    ├─ rates (20-30K расценок)
    ├─ rates_fts (FTS5 индекс)
    └─ resources (500K ресурсов)
    │
    ↓
API / MCP Server (опционально)
    └─ Claude Code Agent для NL запросов
```

## 📂 Структура проекта

```
n8npiplines-bim/
├── src/
│   ├── database/          # Управление БД
│   │   ├── db_manager.py  # Менеджер подключений SQLite
│   │   ├── fts_config.py  # Конфигурация FTS5
│   │   └── schema.sql     # Схема БД
│   ├── etl/               # ETL процессы
│   │   ├── excel_loader.py      # Загрузка Excel файлов
│   │   └── data_aggregator.py   # Агрегация данных
│   └── utils/             # Утилиты
│       ├── text_processor.py    # Обработка текста
│       └── resource_classifier.py # Классификация ресурсов
├── tests/                 # Тесты (pytest)
├── data/
│   ├── raw/              # Исходные Excel файлы
│   └── processed/        # SQLite база данных
├── docs/
│   └── tasks/            # Управление задачами
├── requirements.txt      # Зависимости Python
└── README.md            # Этот файл
```

## 🚀 Быстрый старт

### Требования

- Python 3.8+
- pip

### Установка

```bash
# Клонировать репозиторий
git clone <repository-url>
cd n8npiplines-bim

# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt
```

### Запуск ETL процесса

```bash
# Поместить Excel файл в data/raw/
# Запустить загрузку
python scripts/load_data.py
```

### Запуск тестов

```bash
# Запустить все тесты
pytest

# С покрытием кода
pytest --cov=src --cov-report=html

# Конкретный модуль
pytest tests/test_db_manager.py -v
```

## 🔍 Примеры использования

### Базовый поиск (Python API)

```python
from src.database.db_manager import DatabaseManager

# Подключение к БД
with DatabaseManager('data/processed/estimates.db') as db:
    # Полнотекстовый поиск
    results = db.execute_query("""
        SELECT rate_code, rate_full_name, cost_per_unit
        FROM rates_fts
        WHERE rates_fts MATCH 'перегородки гипсокартон'
        LIMIT 10
    """)

    for rate_code, name, cost in results:
        print(f"{rate_code}: {name} - {cost} руб.")
```

### Расчет стоимости

```python
# Рассчитать стоимость для 150 м²
result = db.execute_query("""
    SELECT
        rate_full_name,
        ROUND((total_cost / unit_quantity) * ?, 2) AS calculated_cost
    FROM rates
    WHERE rate_code = ?
""", (150, "10-05-001-01"))

print(f"Стоимость: {result[0][1]} руб.")
```

## 📊 Структура данных

### Таблица `rates`

| Поле | Тип | Описание |
|------|-----|----------|
| `rate_code` | TEXT | Уникальный код расценки (10-05-001-01) |
| `rate_full_name` | TEXT | Полное наименование работы |
| `unit_quantity` | REAL | Базовое количество единиц (100) |
| `unit_type` | TEXT | Тип единицы измерения (м2, м3, шт) |
| `total_cost` | REAL | Общая стоимость за базовую единицу |
| `materials_cost` | REAL | Стоимость материалов |
| `resources_cost` | REAL | Стоимость работ и техники |

### Таблица `resources`

Детализация ресурсов для каждой расценки (материалы, труд, техника, электроэнергия).

## 🧪 Тестирование

Проект использует pytest с покрытием кода через pytest-cov.

```bash
# Запустить тесты с подробным выводом
pytest -v

# Посмотреть покрытие кода
pytest --cov=src --cov-report=term-missing
```

Тестируемые модули:
- `test_db_manager.py` - управление БД
- `test_fts_config.py` - конфигурация FTS5
- `test_excel_loader.py` - загрузка Excel
- `test_data_aggregator.py` - агрегация данных
- `test_text_processor.py` - обработка текста

## 🔧 Конфигурация

### SQLite оптимизации

База данных настроена с оптимизациями для производительности:

- **WAL mode** - Write-Ahead Logging для конкурентного доступа
- **Cache size** - 64MB для быстрых запросов
- **FTS5** - Full-Text Search с поддержкой русского языка

### Переменные окружения

Создайте файл `.env` для конфигурации:

```env
DB_PATH=data/processed/estimates.db
LOG_LEVEL=INFO
```

## 📈 Производительность

- **Поиск**: <100ms для полнотекстового поиска среди 20-30K расценок
- **Размер БД**: ~50-100MB (основные данные) + ~50-100MB (FTS индексы)
- **Загрузка данных**: ~2-5 минут для 740K строк

## 🛣️ Roadmap

### Фаза 1: MVP (✅ Завершено)
- [x] SQLite БД с FTS5
- [x] ETL процесс
- [x] Базовый поиск и расчет
- [x] Тесты покрытия

### Фаза 2: Оптимизация (В разработке)
- [ ] MCP сервер для Claude API
- [ ] Кэширование частых запросов
- [ ] Web UI
- [ ] API документация

### Фаза 3: Advanced Features
- [ ] Сравнение региональных цен
- [ ] Интеграция с BIM моделями
- [ ] Экспорт в сметные программы
- [ ] Мобильное приложение

## 📝 Документация

Полная архитектурная документация доступна в файле [estimates_search_architecture.md](estimates_search_architecture.md).

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменений (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

### Правила разработки

- Все изменения должны иметь тесты
- Запускайте `pytest` перед коммитом
- Используйте type hints в Python коде

## 📄 Лицензия

MIT License - см. файл LICENSE для деталей

## 👥 Авторы

- Виктор Холостяков - AI-энтузиаст (https://ai.godkod.ru https://t.me/god_kod_ai)

## 🙏 Благодарности

- SQLite за производительную встраиваемую БД
- Anthropic Claude за возможности NL обработки
- pytest за удобный фреймворк тестирования

---

**Вопросы или проблемы?** Создайте issue в репозитории или свяжитесь с командой разработки.
