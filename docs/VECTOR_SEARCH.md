# Vector Search Integration Guide

Семантический поиск расценок с использованием векторных эмбеддингов.

## Обзор

Векторный поиск дополняет полнотекстовый FTS5 поиск **семантическим пониманием** запросов. Вместо точного совпадения ключевых слов, векторный поиск находит расценки с похожим **смыслом**.

### Возможности

- **Семантический поиск**: Находит расценки по смыслу, а не по точным словам
- **Multilingual**: Работает с русским и английским языком
- **Гибридный подход**: Комбинируется с FTS5 для максимального recall
- **Быстрая производительность**: sqlite-vec обеспечивает эффективный поиск

### Технологии

- **Модель**: BAAI/bge-m3 (1024 dimensions)
- **Хранилище**: SQLite + sqlite-vec extension
- **Framework**: sentence-transformers

---

## Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

Будут установлены:
- `sqlite-vec>=0.1.1` - векторное расширение для SQLite
- `sentence-transformers>=2.2.0` - модель эмбеддингов
- `torch>=2.0.0` - PyTorch backend

### 2. Миграция базы данных

Добавляет колонку `embedding` в таблицу `rates`:

```bash
sqlite3 data/processed/estimates.db < migrations/add_vector_embeddings.sql
```

### 3. Генерация эмбеддингов

Генерирует векторные представления для всех расценок (занимает 1-2 часа для 30K расценок):

```bash
python scripts/generate_embeddings.py
```

**Опции:**
- `--batch-size 100` - размер батча (по умолчанию 100)
- `--resume` - продолжить с момента остановки
- `--db-path` - путь к базе данных
- `--model` - название модели (по умолчанию BAAI/bge-m3)

**Пример с GPU:**
```bash
# Использует CUDA если доступна
python scripts/generate_embeddings.py --batch-size 500
```

**Пример resume:**
```bash
# Если процесс был прерван
python scripts/generate_embeddings.py --resume
```

### 4. Использование через MCP

Векторный поиск доступен как MCP tool `vector_search()`:

```python
# Поиск по семантике
result = vector_search(
    query="утепление стен минеральной ватой",
    limit=10,
    similarity_threshold=0.7
)

# С фильтром по единице измерения
result = vector_search(
    query="монолитный бетон для фундамента",
    unit_type="м3",
    limit=5
)
```

---

## API Reference

### MCP Tool: vector_search()

```python
def vector_search(
    query: str,
    limit: int = 10,
    unit_type: str = None,
    similarity_threshold: float = 0.0
) -> str
```

**Параметры:**
- `query` (str) - Текстовый запрос на русском/английском
- `limit` (int) - Максимальное количество результатов (1-100, default: 10)
- `unit_type` (str, optional) - Фильтр по единице измерения ("м2", "м3", "т")
- `similarity_threshold` (float) - Минимальная схожесть 0-1 (default: 0.0)

**Возвращает:**
JSON с результатами:

```json
{
  "success": true,
  "count": 5,
  "query": "утепление стен минеральной ватой",
  "search_method": "vector_similarity",
  "model": "BAAI/bge-m3",
  "results": [
    {
      "rate_code": "10-02-001",
      "rate_full_name": "Утепление стен минеральной ватой толщиной 100 мм",
      "unit_measure_full": "100 м2 стен",
      "cost_per_unit": 450.0,
      "total_cost": 45000.0,
      "similarity": 0.9234,
      "distance": 0.0766
    }
  ]
}
```

### Python API: VectorSearchEngine

```python
from src.search.vector_engine import VectorSearchEngine
from src.database.db_manager import DatabaseManager

# Инициализация
db = DatabaseManager("data/processed/estimates.db")
db.connect()
vector_engine = VectorSearchEngine(db)

# Поиск
results = vector_engine.search(
    query="перегородки гипсокартон",
    limit=10,
    filters={'unit_type': 'м2'},
    similarity_threshold=0.6
)

# Статистика эмбеддингов
stats = vector_engine.get_embedding_stats()
print(stats)
# {
#   'total_rates': 30000,
#   'embedded_rates': 30000,
#   'missing_embeddings': 0,
#   'embedding_coverage': 100.0,
#   'model_name': 'BAAI/bge-m3'
# }
```

---

## Примеры использования

### Пример 1: Концептуальный поиск

**FTS5 (ключевые слова):**
```python
natural_search("перегородки гипсокартон")
# Найдет только расценки с точными словами "перегородки" И "гипсокартон"
```

**Vector Search (семантика):**
```python
vector_search("внутренние стены из листового материала")
# Найдет:
# - Перегородки из гипсокартона
# - Перегородки из ГВЛ
# - Облицовка стен листовыми материалами
# Даже если точные слова не совпадают!
```

### Пример 2: Гибридный подход

Комбинирование FTS5 и векторного поиска для максимального recall:

```python
# Получить результаты от обоих методов
fts_results = natural_search("бетон фундамент", limit=20)
vector_results = vector_search("бетон фундамент", limit=20, similarity_threshold=0.5)

# Объединить и ре-ранкировать по relevance
combined = merge_and_rerank(fts_results, vector_results)
```

### Пример 3: Поиск с высокой точностью

```python
# Только очень похожие результаты
vector_search(
    query="устройство монолитного ленточного фундамента",
    limit=5,
    similarity_threshold=0.85
)
# Вернет только высокорелевантные расценки
```

---

## Производительность

### Скорость генерации эмбеддингов

| Конфигурация | Скорость | Время для 30K расценок |
|--------------|----------|------------------------|
| CPU (8 cores) | ~50 rates/sec | ~10 минут |
| GPU (NVIDIA T4) | ~500 rates/sec | ~1 минута |
| GPU (NVIDIA A100) | ~2000 rates/sec | ~15 секунд |

### Скорость поиска

| Операция | Время |
|----------|-------|
| Генерация query embedding | ~50ms (CPU), ~5ms (GPU) |
| Vector similarity search (30K rates) | ~100-200ms |
| Total query time | ~150-250ms |

### Размер хранилища

- **Embedding column**: ~120MB для 30K расценок (1024 dims × 4 bytes × 30K)
- **Индекс**: Дополнительно ~50MB (при использовании vec0 индекса)
- **Общее увеличение БД**: ~170MB

---

## Сравнение FTS5 vs Vector Search

| Критерий | FTS5 | Vector Search |
|----------|------|---------------|
| **Тип поиска** | Точное совпадение ключевых слов | Семантическое сходство |
| **Скорость** | Очень быстро (<50ms) | Быстро (~150ms) |
| **Recall** | Средний (нужны точные слова) | Высокий (понимает синонимы) |
| **Precision** | Высокая | Средняя (может найти "лишнее") |
| **Требования** | Минимальные | Требует генерации эмбеддингов |
| **Размер** | Минимальный (~50MB индекс) | Средний (~170MB) |

### Когда использовать что?

**FTS5 (natural_search):**
- Пользователь знает точные термины
- Нужна максимальная скорость
- Поиск по кодам расценок
- Простые ключевые слова

**Vector Search (vector_search):**
- Концептуальные запросы ("как сделать теплую стену")
- Поиск синонимов и вариаций
- Запросы на естественном языке
- Неточное описание работ

**Hybrid (оба метода):**
- Максимальный recall + precision
- Комплексные запросы
- Исследовательский поиск

---

## Troubleshooting

### Проблема: Медленная генерация эмбеддингов

**Решение:**
```bash
# Проверить доступность GPU
python -c "import torch; print(torch.cuda.is_available())"

# Если GPU доступен, увеличить batch size
python scripts/generate_embeddings.py --batch-size 1000

# Использовать меньшую модель (быстрее, но хуже качество)
python scripts/generate_embeddings.py --model "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
```

### Проблема: sqlite-vec не найден

**Решение:**
```bash
# Переустановить sqlite-vec
pip uninstall sqlite-vec
pip install sqlite-vec>=0.1.1

# Проверить импорт
python -c "import sqlite_vec; print('OK')"
```

### Проблема: Недостаточно памяти

**Решение:**
```bash
# Уменьшить batch size
python scripts/generate_embeddings.py --batch-size 10

# Использовать более легкую модель
python scripts/generate_embeddings.py --model "sentence-transformers/distiluse-base-multilingual-cased-v2"
```

### Проблема: Низкое качество поиска

**Решение:**
1. Проверить, что эмбеддинги сгенерированы:
```python
stats = vector_engine.get_embedding_stats()
print(stats['embedding_coverage'])  # Должно быть 100.0
```

2. Увеличить similarity_threshold для более строгого поиска
3. Использовать более мощную модель (BGE-M3 лучше всего для русского)

---

## Дальнейшее развитие

### Возможные улучшения

1. **Гибридный ре-ранкинг**: Комбинирование FTS5 + Vector + LLM для ре-ранкинга
2. **Кэширование**: Кэшировать частые query embeddings
3. **Fine-tuning**: Дообучить модель на строительных данных
4. **Feedback loop**: Учитывать клики пользователей для улучшения relevance

### Alternative Models

| Модель | Dims | Качество (Russian) | Скорость |
|--------|------|-------------------|----------|
| **BAAI/bge-m3** | 1024 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| GigaEmbeddings | 768 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| ru-en-RoSBERTa | 768 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Multilingual E5-large | 1024 | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| distiluse-multilingual | 512 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## Ссылки

- [BGE-M3 Model Card](https://huggingface.co/BAAI/bge-m3)
- [sqlite-vec Documentation](https://github.com/asg017/sqlite-vec)
- [sentence-transformers Documentation](https://www.sbert.net/)
- [ruMTEB Benchmark](https://arxiv.org/abs/2408.12503)

---

**Вопросы?** Создайте issue в репозитории.
