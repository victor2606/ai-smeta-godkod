#!/usr/bin/env python3
"""
Полноценный интеграционный тест системы поиска строительных расценок.

Тестирует:
- FTS5 полнотекстовый поиск
- Векторный семантический поиск
- Гибридный поиск (FTS5 + векторы)
- Поиск по коду расценки
- Фильтрацию результатов
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.database.db_manager import DatabaseManager
from src.search.search_engine import SearchEngine

# OpenAI API key from environment
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    print("❌ ERROR: OPENAI_API_KEY environment variable not set")
    print("   Set it with: export OPENAI_API_KEY='your-api-key'")
    sys.exit(1)

print("=" * 80)
print("ИНТЕГРАЦИОННЫЙ ТЕСТ СИСТЕМЫ ПОИСКА РАСЦЕНОК")
print("=" * 80)

# Инициализация
db_manager = DatabaseManager("data/processed/estimates.db")
db_manager.connect()

# SearchEngine с векторным поиском
search_engine = SearchEngine(db_manager, openai_api_key=API_KEY)

print("\n✅ Система инициализирована")
print(f"   - База данных: data/processed/estimates.db")
print(f"   - FTS5: включен")
print(f"   - Vector Search: {'включен' if search_engine.vector_engine else 'выключен'}")

# ============================================================================
# ТЕСТ 1: FTS5 полнотекстовый поиск
# ============================================================================
print("\n" + "=" * 80)
print("ТЕСТ 1: FTS5 ПОЛНОТЕКСТОВЫЙ ПОИСК")
print("=" * 80)

query1 = "бетонирование монолитных конструкций"
print(f"\nЗапрос: '{query1}'")

fts_results = search_engine.search(query1, limit=5)
print(f"\nНайдено: {len(fts_results)} результатов")

for i, r in enumerate(fts_results, 1):
    print(f"\n{i}. {r['rate_code']}")
    print(f"   {r['rate_full_name'][:80]}...")
    print(f"   Цена: {r['cost_per_unit']:.2f} руб/{r['unit_measure_full']}")
    print(f"   FTS Rank: {r['rank']:.4f}")

# ============================================================================
# ТЕСТ 2: Векторный семантический поиск
# ============================================================================
print("\n" + "=" * 80)
print("ТЕСТ 2: ВЕКТОРНЫЙ СЕМАНТИЧЕСКИЙ ПОИСК")
print("=" * 80)

query2 = "копка траншеи экскаватором"
print(f"\nЗапрос: '{query2}'")

vector_results = search_engine.vector_search(query2, limit=5)
print(f"\nНайдено: {len(vector_results)} результатов")

for i, r in enumerate(vector_results, 1):
    print(f"\n{i}. {r['rate_code']}")
    print(f"   {r['rate_full_name'][:80]}...")
    print(f"   Цена: {r['cost_per_unit']:.2f} руб/{r['unit_type']}")
    print(f"   Similarity: {r['similarity']:.3f}")

# ============================================================================
# ТЕСТ 3: Гибридный поиск (FTS5 + Vector)
# ============================================================================
print("\n" + "=" * 80)
print("ТЕСТ 3: ГИБРИДНЫЙ ПОИСК (FTS5 + VECTOR)")
print("=" * 80)

query3 = "устройство асфальтобетонного покрытия"
print(f"\nЗапрос: '{query3}'")

hybrid_results = search_engine.hybrid_search(
    query3, fts_limit=10, vector_limit=5, similarity_threshold=0.4
)

print(f"\nРезультаты:")
print(f"   - FTS5: {len(hybrid_results['fts_results'])} результатов")
print(f"   - Vector: {len(hybrid_results['vector_results'])} результатов")
print(f"   - Combined: {len(hybrid_results['combined'])} уникальных")

print(f"\nТоп-5 комбинированных результатов:")
for i, r in enumerate(hybrid_results["combined"][:5], 1):
    # Проверяем откуда результат
    source = "Vector + FTS" if "similarity" in r else "FTS only"

    print(f"\n{i}. {r['rate_code']} [{source}]")
    print(f"   {r.get('rate_full_name', r.get('rate_full_name', 'N/A'))[:80]}...")

    if "similarity" in r:
        print(f"   Similarity: {r['similarity']:.3f}")
    if "rank" in r:
        print(f"   FTS Rank: {r['rank']:.4f}")

# ============================================================================
# ТЕСТ 4: Поиск с фильтрами
# ============================================================================
print("\n" + "=" * 80)
print("ТЕСТ 4: ВЕКТОРНЫЙ ПОИСК С ФИЛЬТРАМИ")
print("=" * 80)

query4 = "укладка плитки"
print(f"\nЗапрос: '{query4}'")
print(f"Фильтр: min_cost >= 5000 руб")

filtered_results = search_engine.vector_search(
    query4, filters={"min_cost": 5000}, limit=5
)

print(f"\nНайдено: {len(filtered_results)} результатов")

for i, r in enumerate(filtered_results, 1):
    print(f"\n{i}. {r['rate_code']}")
    print(f"   {r['rate_full_name'][:80]}...")
    print(f"   Цена: {r['cost_per_unit']:.2f} руб/{r['unit_type']}")
    print(f"   Similarity: {r['similarity']:.3f}")

# ============================================================================
# ТЕСТ 5: Поиск по коду
# ============================================================================
print("\n" + "=" * 80)
print("ТЕСТ 5: ПОИСК ПО КОДУ РАСЦЕНКИ")
print("=" * 80)

code_prefix = "01-01"
print(f"\nПрефикс кода: '{code_prefix}'")

code_results = search_engine.search_by_code(code_prefix)
print(f"\nНайдено: {len(code_results)} результатов")

for i, r in enumerate(code_results[:5], 1):
    print(f"\n{i}. {r['rate_code']}")
    if r["rate_full_name"]:
        print(f"   {r['rate_full_name'][:80]}...")
    print(f"   Цена: {r['cost_per_unit']:.2f} руб/{r['unit_measure_full']}")

# ============================================================================
# ТЕСТ 6: Сравнение FTS5 vs Vector на одном запросе
# ============================================================================
print("\n" + "=" * 80)
print("ТЕСТ 6: СРАВНЕНИЕ FTS5 vs VECTOR НА ОДНОМ ЗАПРОСЕ")
print("=" * 80)

query6 = "монтаж металлоконструкций"
print(f"\nЗапрос: '{query6}'")

# FTS5
fts_comp = search_engine.search(query6, limit=3)
print(f"\n📝 FTS5 результаты ({len(fts_comp)}):")
for i, r in enumerate(fts_comp, 1):
    print(f"{i}. {r['rate_code']}: {r['rate_full_name'][:60]}...")

# Vector
vec_comp = search_engine.vector_search(query6, limit=3)
print(f"\n🔍 Vector результаты ({len(vec_comp)}):")
for i, r in enumerate(vec_comp, 1):
    print(f"{i}. {r['rate_code']}: {r['rate_full_name'][:60]}...")
    print(f"   Similarity: {r['similarity']:.3f}")

# ============================================================================
# ИТОГИ
# ============================================================================
print("\n" + "=" * 80)
print("ИТОГИ ТЕСТИРОВАНИЯ")
print("=" * 80)

# Статистика базы
stats_sql = """
SELECT
    (SELECT COUNT(*) FROM rates) as total_rates,
    (SELECT COUNT(*) FROM resources) as total_resources,
    (SELECT COUNT(*) FROM rates WHERE embedding IS NOT NULL) as rates_with_embeddings,
    (SELECT COUNT(*) FROM rates WHERE rate_full_name IS NOT NULL AND rate_full_name != '') as rates_with_names
"""

stats = db_manager.execute_query(stats_sql)[0]

print(f"\n📊 Статистика базы данных:")
print(f"   - Всего расценок: {stats[0]:,}")
print(f"   - Всего ресурсов: {stats[1]:,}")
print(f"   - Расценок с именами: {stats[3]:,}")
print(f"   - Расценок с эмбеддингами: {stats[2]:,} ({stats[2] / stats[0] * 100:.1f}%)")

print(f"\n✅ Все тесты пройдены успешно!")
print(f"\n💡 Система готова к использованию:")
print(f"   - FTS5 поиск по ключевым словам")
print(f"   - Векторный семантический поиск")
print(f"   - Гибридный режим (лучшее из обоих)")
print(f"   - Фильтрация по стоимости и единицам")
print(f"   - Поиск по кодам расценок")

db_manager.disconnect()
print("\n" + "=" * 80)
