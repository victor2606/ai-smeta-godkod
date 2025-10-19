"""
Unit Tests for FTS5 Configuration Module

Tests for Russian language full-text search query preparation including:
- Text normalization
- Stopword removal
- Wildcard addition
- Synonym expansion
- Complete query preparation pipeline
"""

import pytest
from src.database.fts_config import (
    normalize_text,
    remove_stopwords,
    add_wildcards,
    expand_synonyms,
    prepare_fts_query,
    get_stopwords,
    get_synonyms,
    add_custom_stopword,
    add_custom_synonym,
    RUSSIAN_STOPWORDS,
    SYNONYMS
)


# ============================================================================
# Test: normalize_text()
# ============================================================================

class TestNormalizeText:
    """Test suite for text normalization function."""

    def test_lowercase_conversion(self):
        """Test that text is converted to lowercase."""
        assert normalize_text("УСТРОЙСТВО ПЕРЕГОРОДОК") == "устройство перегородок"
        assert normalize_text("ГКЛ") == "гкл"
        assert normalize_text("МиКс РеГиСтРа") == "микс регистра"

    def test_special_character_removal(self):
        """Test removal of special characters."""
        assert normalize_text("устройство!!! перегородок???") == "устройство перегородок"
        assert normalize_text("ГКЛ-12.5мм") == "гкл 12 5мм"
        assert normalize_text("монтаж (двойной)") == "монтаж двойной"
        assert normalize_text("цена: 1,500.00 руб.") == "цена 1 500 00 руб"

    def test_whitespace_normalization(self):
        """Test collapsing multiple spaces and trimming."""
        assert normalize_text("   много   пробелов   ") == "много пробелов"
        assert normalize_text("один\t\tтаб") == "один таб"
        assert normalize_text("новая\nстрока") == "новая строка"

    def test_cyrillic_preservation(self):
        """Test that Cyrillic characters are preserved."""
        assert normalize_text("абвгдеёжзийклмнопрстуфхцчшщъыьэюя") == "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"

    def test_latin_preservation(self):
        """Test that Latin characters are preserved."""
        assert normalize_text("ABCXYZ") == "abcxyz"

    def test_digit_preservation(self):
        """Test that digits are preserved."""
        assert normalize_text("150 м2") == "150 м2"
        assert normalize_text("ГКЛ-12.5") == "гкл 12 5"

    def test_empty_and_none(self):
        """Test handling of empty strings and None."""
        assert normalize_text("") == ""
        assert normalize_text("   ") == ""
        assert normalize_text(None) == ""

    def test_only_special_characters(self):
        """Test text with only special characters."""
        assert normalize_text("!!!???...") == ""
        assert normalize_text("@#$%^&*()") == ""


# ============================================================================
# Test: remove_stopwords()
# ============================================================================

class TestRemoveStopwords:
    """Test suite for stopword removal function."""

    def test_basic_stopword_removal(self):
        """Test removal of common Russian stopwords."""
        assert remove_stopwords("устройство перегородок из гипсокартона") == "устройство перегородок гипсокартона"
        assert remove_stopwords("монтаж конструкций в здании") == "монтаж конструкций здании"
        assert remove_stopwords("работы по укладке плитки") == "работы укладке плитки"

    def test_multiple_stopwords(self):
        """Test removal of multiple consecutive stopwords."""
        assert remove_stopwords("работы по и для монтажа") == "работы монтажа"
        assert remove_stopwords("из в на по с к") == ""

    def test_no_stopwords(self):
        """Test text without stopwords."""
        assert remove_stopwords("устройство перегородок гипсокартон") == "устройство перегородок гипсокартон"

    def test_only_stopwords(self):
        """Test text containing only stopwords."""
        assert remove_stopwords("из в на по с к для") == ""

    def test_empty_input(self):
        """Test with empty string."""
        assert remove_stopwords("") == ""

    def test_custom_stopwords(self):
        """Test with custom stopword set."""
        custom_stopwords = {'тест', 'пример'}
        assert remove_stopwords("тест пример слово", custom_stopwords) == "слово"


# ============================================================================
# Test: add_wildcards()
# ============================================================================

class TestAddWildcards:
    """Test suite for wildcard addition function."""

    def test_basic_wildcard_addition(self):
        """Test adding wildcards to words."""
        assert add_wildcards("устройство перегородок гкл") == "устройство* перегородок* гкл*"
        assert add_wildcards("монтаж конструкций") == "монтаж* конструкций*"

    def test_min_word_length_threshold(self):
        """Test that short words don't get wildcards."""
        assert add_wildcards("а в устройство", min_word_length=3) == "а в устройство*"
        assert add_wildcards("из на монтаж", min_word_length=3) == "из на монтаж*"

    def test_custom_min_length(self):
        """Test with custom minimum word length."""
        assert add_wildcards("гкл монтаж", min_word_length=5) == "гкл монтаж*"
        assert add_wildcards("ab cd устройство", min_word_length=2) == "ab* cd* устройство*"

    def test_empty_input(self):
        """Test with empty string."""
        assert add_wildcards("") == ""

    def test_single_character_words(self):
        """Test with single character words."""
        assert add_wildcards("а б в гкл", min_word_length=3) == "а б в гкл*"


# ============================================================================
# Test: expand_synonyms()
# ============================================================================

class TestExpandSynonyms:
    """Test suite for synonym expansion function."""

    def test_gkl_synonym_expansion(self):
        """Test ГКЛ/гипсокартон synonym expansion."""
        result = expand_synonyms("перегородки гкл")
        assert "гкл" in result or "гипсокартон" in result
        assert "OR" in result

    def test_m2_synonym_expansion(self):
        """Test м2/квадратный метр synonym expansion."""
        result = expand_synonyms("площадь м2")
        assert "м2" in result
        assert "OR" in result

    def test_m3_synonym_expansion(self):
        """Test м3/кубический метр synonym expansion."""
        result = expand_synonyms("объем м3")
        assert "м3" in result
        assert "OR" in result

    def test_no_synonyms(self):
        """Test text without synonyms."""
        assert expand_synonyms("монтаж конструкций") == "монтаж конструкций"

    def test_multiple_synonyms(self):
        """Test text with multiple synonym words."""
        result = expand_synonyms("гкл м2")
        assert "OR" in result
        # Should have two OR clauses
        assert result.count("OR") >= 2

    def test_empty_input(self):
        """Test with empty string."""
        assert expand_synonyms("") == ""

    def test_custom_synonyms(self):
        """Test with custom synonym dictionary."""
        custom_synonyms = {'тест': ['испытание', 'проверка']}
        result = expand_synonyms("тест качества", custom_synonyms)
        assert "тест" in result
        assert "испытание" in result
        assert "проверка" in result
        assert "OR" in result


# ============================================================================
# Test: prepare_fts_query() - Main Function
# ============================================================================

class TestPrepareFTSQuery:
    """Test suite for the main query preparation function."""

    def test_complete_pipeline(self):
        """Test the complete query preparation pipeline."""
        query = "устройство перегородок из ГКЛ 150 м2"
        result = prepare_fts_query(query)

        # Should be normalized (lowercase)
        assert result.islower() or "OR" in result  # OR clauses may have uppercase

        # Should have wildcards
        assert "*" in result

        # Should have synonym expansion
        assert "OR" in result

        # Original words should be present
        assert "устройство" in result.lower()
        assert "перегородок" in result.lower()

    def test_with_special_characters(self):
        """Test query with special characters."""
        query = "Монтаж!!! конструкций???"
        result = prepare_fts_query(query)

        assert "монтаж" in result.lower()
        assert "конструкций" in result.lower()
        assert "!" not in result
        assert "?" not in result

    def test_with_stopwords(self):
        """Test that stopwords are removed."""
        query = "работы по устройству перегородок из гипсокартона"
        result = prepare_fts_query(query)

        # Stopwords should be removed
        assert " по " not in result
        assert " из " not in result

        # Content words should remain
        assert "работы" in result.lower()
        assert "устройству" in result.lower() or "устройство" in result.lower()

    def test_synonym_expansion_gkl(self):
        """Test ГКЛ synonym expansion in full pipeline."""
        query = "перегородки ГКЛ"
        result = prepare_fts_query(query)

        # Should contain both гкл and гипсокартон with OR
        assert "гкл" in result.lower()
        assert "OR" in result

    def test_empty_query_raises_error(self):
        """Test that empty query raises ValueError."""
        with pytest.raises(ValueError, match="Query is empty"):
            prepare_fts_query("")

        with pytest.raises(ValueError, match="Query is empty"):
            prepare_fts_query("   ")

    def test_none_query_raises_error(self):
        """Test that None query raises ValueError."""
        with pytest.raises(ValueError, match="Query cannot be None"):
            prepare_fts_query(None)

    def test_only_stopwords_query(self):
        """Test query containing only stopwords."""
        query = "из в на по с"
        result = prepare_fts_query(query)

        # Should fall back to normalized version
        assert isinstance(result, str)
        assert len(result) > 0

    def test_numeric_query(self):
        """Test query with numbers."""
        query = "150 м2"
        result = prepare_fts_query(query)

        assert "150" in result
        assert "м2" in result.lower() or "OR" in result

    def test_mixed_case_query(self):
        """Test query with mixed case."""
        query = "УстРОйСтво ПеРеГоРоДоК"
        result = prepare_fts_query(query)

        # Should be normalized to lowercase
        assert "устройство" in result.lower()
        assert "перегородок" in result.lower()


# ============================================================================
# Test: Utility Functions
# ============================================================================

class TestUtilityFunctions:
    """Test suite for utility functions."""

    def test_get_stopwords(self):
        """Test retrieving stopwords set."""
        stopwords = get_stopwords()
        assert isinstance(stopwords, set)
        assert 'из' in stopwords
        assert 'в' in stopwords
        assert 'на' in stopwords

    def test_get_synonyms(self):
        """Test retrieving synonyms dictionary."""
        synonyms = get_synonyms()
        assert isinstance(synonyms, dict)
        assert 'гкл' in synonyms
        assert 'гипсокартон' in synonyms['гкл']

    def test_add_custom_stopword(self):
        """Test adding custom stopword."""
        initial_count = len(RUSSIAN_STOPWORDS)
        add_custom_stopword("тестовоеслово")
        assert len(RUSSIAN_STOPWORDS) == initial_count + 1
        assert "тестовоеслово" in RUSSIAN_STOPWORDS

        # Test normalization
        add_custom_stopword("  ДРУГОЕСЛОВО  ")
        assert "другоеслово" in RUSSIAN_STOPWORDS

    def test_add_custom_synonym(self):
        """Test adding custom synonym."""
        add_custom_synonym("тест", ["испытание", "проверка"])
        assert "тест" in SYNONYMS
        assert "испытание" in SYNONYMS["тест"]
        assert "проверка" in SYNONYMS["тест"]


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    def test_very_long_query(self):
        """Test with very long query."""
        long_query = " ".join(["слово"] * 100)
        result = prepare_fts_query(long_query)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_single_word_query(self):
        """Test with single word."""
        result = prepare_fts_query("монтаж")
        assert "монтаж" in result.lower()
        assert "*" in result

    def test_query_with_only_numbers(self):
        """Test query with only numbers."""
        result = prepare_fts_query("150")
        assert "150" in result

    def test_query_with_mixed_cyrillic_latin(self):
        """Test query with mixed Cyrillic and Latin."""
        result = prepare_fts_query("ГКЛ GCL монтаж")
        assert "гкл" in result.lower()
        assert "gcl" in result.lower()
        assert "монтаж" in result.lower()

    def test_unicode_handling(self):
        """Test proper Unicode/UTF-8 handling."""
        query = "устройство перегородок"
        result = prepare_fts_query(query)
        assert isinstance(result, str)
        # Should handle Cyrillic properly
        assert "устройство" in result.lower()


# ============================================================================
# Test: Real-World Scenarios
# ============================================================================

class TestRealWorldScenarios:
    """Test suite with real construction query examples."""

    def test_partition_wall_query(self):
        """Test typical partition wall query."""
        query = "устройство перегородок из ГКЛ в один слой"
        result = prepare_fts_query(query)

        assert "устройство" in result.lower()
        assert "перегородок" in result.lower()
        assert "слой" in result.lower()
        # Stopwords should be removed
        assert " из " not in result.lower() or "OR" in result
        assert " в " not in result.lower() or "OR" in result

    def test_area_calculation_query(self):
        """Test query with area measurement."""
        query = "сколько стоит 150 квадратных метров"
        result = prepare_fts_query(query)

        assert "150" in result
        assert "квадратных" in result.lower() or "OR" in result

    def test_material_search_query(self):
        """Test material-specific search."""
        query = "расход гипсокартона на м2"
        result = prepare_fts_query(query)

        assert "расход" in result.lower()
        # гипсокартона should be stemmed to гипсокартон or similar
        assert "гипсокартон" in result.lower()

    def test_comparison_query(self):
        """Test comparison query."""
        query = "сравнить однослойные и двухслойные перегородки"
        result = prepare_fts_query(query)

        assert "сравнить" in result.lower()
        assert "однослойные" in result.lower()
        assert "двухслойные" in result.lower()


# ============================================================================
# Pytest Fixtures
# ============================================================================

@pytest.fixture
def sample_queries():
    """Fixture providing sample queries for testing."""
    return [
        "устройство перегородок из ГКЛ",
        "монтаж конструкций 150 м2",
        "укладка плитки в помещении",
        "расход материалов на 100 м3",
    ]


@pytest.fixture
def expected_transformations():
    """Fixture providing expected query transformations."""
    return {
        "ГКЛ": "гкл",
        "150 М2": "150 м2",
        "УСТРОЙСТВО!!!": "устройство",
    }


def test_with_sample_queries(sample_queries):
    """Test batch processing of sample queries."""
    for query in sample_queries:
        result = prepare_fts_query(query)
        assert isinstance(result, str)
        assert len(result) > 0
        assert "*" in result  # Should have wildcards
