#!/usr/bin/env python3
"""Test vector search functionality with OpenAI embeddings."""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.database.db_manager import DatabaseManager
from src.search.vector_engine import VectorSearchEngine

# OpenAI API key from environment
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    print("❌ ERROR: OPENAI_API_KEY environment variable not set")
    print("   Set it with: export OPENAI_API_KEY='your-api-key'")
    sys.exit(1)

# Initialize
db_manager = DatabaseManager("data/processed/estimates.db")
db_manager.connect()

vector_engine = VectorSearchEngine(db_manager, api_key=API_KEY)

print("🔍 Тест векторного поиска\n")

# Test 1: Semantic search for concrete work
print("=" * 60)
print("Тест 1: Поиск 'бетонные работы'")
print("=" * 60)
results = vector_engine.search("бетонные работы", limit=5)

for i, r in enumerate(results, 1):
    print(f"\n{i}. {r['rate_code']}: {r['rate_full_name']}")
    print(f"   Similarity: {r['similarity']:.3f}")
    print(f"   Unit: {r['unit_type']}")
    print(f"   Cost: {r['cost_per_unit']:.2f} руб/{r['unit_type']}")

# Test 2: Semantic search for excavation
print("\n" + "=" * 60)
print("Тест 2: Поиск 'земляные работы экскаватором'")
print("=" * 60)
results = vector_engine.search("земляные работы экскаватором", limit=5)

for i, r in enumerate(results, 1):
    print(f"\n{i}. {r['rate_code']}: {r['rate_full_name']}")
    print(f"   Similarity: {r['similarity']:.3f}")
    print(f"   Unit: {r['unit_type']}")
    print(f"   Cost: {r['cost_per_unit']:.2f} руб/{r['unit_type']}")

# Test 3: Semantic search with filters
print("\n" + "=" * 60)
print("Тест 3: Поиск 'укладка асфальта' с фильтром по стоимости")
print("=" * 60)
results = vector_engine.search("укладка асфальта", limit=5, filters={"min_cost": 1000})

for i, r in enumerate(results, 1):
    print(f"\n{i}. {r['rate_code']}: {r['rate_full_name']}")
    print(f"   Similarity: {r['similarity']:.3f}")
    print(f"   Unit: {r['unit_type']}")
    print(f"   Cost: {r['cost_per_unit']:.2f} руб/{r['unit_type']}")

# Test 4: Statistics
print("\n" + "=" * 60)
print("Статистика эмбеддингов")
print("=" * 60)
stats = vector_engine.get_embedding_stats()
for key, value in stats.items():
    print(f"{key}: {value}")

db_manager.disconnect()
print("\n✅ Все тесты завершены")
