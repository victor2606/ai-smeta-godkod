"""
FTS5 Configuration Module for Construction Rates Full-Text Search

This module provides configuration and query preparation utilities for SQLite FTS5
full-text search with Russian language support. It handles stopwords, normalization,
wildcard matching, and synonym expansion.
"""

import re
import logging
from typing import Dict, List, Set


# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# Russian Language Stopwords
# ============================================================================

RUSSIAN_STOPWORDS: Set[str] = {
    'из', 'в', 'на', 'по', 'с', 'к', 'для', 'и', 'или', 'а', 'но',
    'за', 'о', 'об', 'от', 'до', 'у', 'без', 'через', 'при', 'про',
    'между', 'среди', 'то', 'же', 'как', 'что', 'это', 'который',
    'весь', 'свой', 'чтобы', 'быть', 'мочь', 'такой', 'этот', 'сам',
    'так', 'вот', 'только', 'уже', 'еще', 'когда', 'где', 'почему'
}


# ============================================================================
# Synonym Mappings
# ============================================================================

SYNONYMS: Dict[str, List[str]] = {
    'гкл': ['гипсокартон'],
    'гипсокартон': ['гкл'],
    'м2': ['квадратный метр', 'кв метр', 'кв м'],
    'квадратный': ['м2', 'кв'],
    'м3': ['кубический метр', 'куб метр', 'куб м'],
    'кубический': ['м3', 'куб'],
    'пм': ['погонный метр', 'пог метр'],
    'погонный': ['пм', 'пог'],
}


# ============================================================================
# Normalization Functions
# ============================================================================

def normalize_text(text: str) -> str:
    """
    Normalize text by removing special characters and standardizing format.

    Performs the following operations:
    1. Converts to lowercase for case-insensitive matching
    2. Removes all special characters except Cyrillic letters, Latin letters, digits, and spaces
    3. Collapses multiple spaces into single space
    4. Strips leading/trailing whitespace

    Args:
        text: Input text string to normalize

    Returns:
        Normalized text string

    Examples:
        >>> normalize_text("Устройство перегородок!!!")
        'устройство перегородок'
        >>> normalize_text("ГКЛ-12.5мм  (двойной)")
        'гкл 12 5мм двойной'
        >>> normalize_text("   Много   пробелов   ")
        'много пробелов'
    """
    if not text:
        return ""

    # Convert to lowercase
    text = text.lower()

    # Keep only Cyrillic, Latin, digits, and spaces
    # Pattern: keep а-я (Cyrillic), a-z (Latin), 0-9 (digits), and spaces
    text = re.sub(r'[^а-яёa-z0-9\s]', ' ', text)

    # Collapse multiple spaces into single space
    text = re.sub(r'\s+', ' ', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    logger.debug(f"Normalized text: '{text}'")
    return text


def remove_stopwords(text: str, stopwords: Set[str] = RUSSIAN_STOPWORDS) -> str:
    """
    Remove stopwords from text while preserving word order.

    Args:
        text: Input text (should be normalized first)
        stopwords: Set of stopwords to remove (defaults to RUSSIAN_STOPWORDS)

    Returns:
        Text with stopwords removed

    Examples:
        >>> remove_stopworks("устройство перегородок из гипсокартона")
        'устройство перегородок гипсокартона'
        >>> remove_stopwords("монтаж конструкций в здании")
        'монтаж конструкций здании'
    """
    if not text:
        return ""

    words = text.split()
    filtered_words = [word for word in words if word not in stopwords]

    result = ' '.join(filtered_words)

    logger.debug(f"Removed stopwords: '{text}' -> '{result}'")
    return result


def add_wildcards(text: str, min_word_length: int = 3) -> str:
    """
    Add wildcard suffix (*) to words for prefix matching in FTS5.

    Only adds wildcards to words that are at least min_word_length characters long.
    This prevents overly broad matching on short words.

    Args:
        text: Input text with space-separated words
        min_word_length: Minimum word length to receive wildcard (default: 3)

    Returns:
        Text with wildcards added to eligible words

    Examples:
        >>> add_wildcards("устройство перегородок гкл")
        'устройство* перегородок* гкл*'
        >>> add_wildcards("устройство из гкл", min_word_length=3)
        'устройство* из гкл*'
        >>> add_wildcards("а в с монтаж", min_word_length=3)
        'а в с монтаж*'
    """
    if not text:
        return ""

    words = text.split()
    wildcard_words = [
        f"{word}*" if len(word) >= min_word_length else word
        for word in words
    ]

    result = ' '.join(wildcard_words)

    logger.debug(f"Added wildcards: '{text}' -> '{result}'")
    return result


def expand_synonyms(text: str, synonym_map: Dict[str, List[str]] = SYNONYMS) -> str:
    """
    Expand words with their synonyms using FTS5 OR operator.

    For each word that has synonyms, creates an OR clause:
    "word" becomes "(word OR synonym1 OR synonym2)"

    Args:
        text: Input text with space-separated words
        synonym_map: Dictionary mapping words to their synonyms

    Returns:
        Text with synonyms expanded using OR clauses

    Examples:
        >>> expand_synonyms("перегородки гкл 150")
        'перегородки (гкл OR гипсокартон) 150'
        >>> expand_synonyms("площадь м2")
        'площадь (м2 OR квадратный OR метр OR кв OR метр OR кв OR м)'
        >>> expand_synonyms("объем м3")
        'объем (м3 OR кубический OR метр OR куб OR метр OR куб OR м)'
    """
    if not text:
        return ""

    words = text.split()
    expanded_words = []

    for word in words:
        if word in synonym_map:
            # Create OR clause: (word OR synonym1 OR synonym2 ...)
            synonyms = synonym_map[word]
            # Flatten multi-word synonyms into individual words
            all_variants = [word] + synonyms
            synonym_clause = f"({' OR '.join(all_variants)})"
            expanded_words.append(synonym_clause)
            logger.debug(f"Expanded synonym: '{word}' -> '{synonym_clause}'")
        else:
            expanded_words.append(word)

    result = ' '.join(expanded_words)

    logger.debug(f"Synonym expansion: '{text}' -> '{result}'")
    return result


# ============================================================================
# Main Query Preparation Function
# ============================================================================

def prepare_fts_query(user_query: str) -> str:
    """
    Prepare a user's natural language query for FTS5 full-text search.

    This is the main function that orchestrates the complete query preparation pipeline:
    1. Normalize text (lowercase, remove special chars, trim spaces)
    2. Remove Russian stopwords
    3. Expand synonyms with OR clauses
    4. Add wildcard suffixes for prefix matching

    Args:
        user_query: Natural language search query from user

    Returns:
        FTS5-compatible query string ready for MATCH clause

    Raises:
        ValueError: If user_query is None or empty after normalization

    Examples:
        >>> prepare_fts_query("устройство перегородок из ГКЛ 150 м2")
        'устройство* перегородок* (гкл* OR гипсокартон*) 150 (м2* OR квадратный* OR метр* OR кв* OR м*)'

        >>> prepare_fts_query("Монтаж конструкций!!!")
        'монтаж* конструкций*'

        >>> prepare_fts_query("   ")
        ValueError: Query is empty after normalization
    """
    # Validate input
    if user_query is None:
        logger.error("prepare_fts_query received None as input")
        raise ValueError("Query cannot be None")

    logger.info(f"Preparing FTS query for: '{user_query}'")

    # Step 1: Normalize text
    normalized = normalize_text(user_query)
    if not normalized:
        logger.error("Query is empty after normalization")
        raise ValueError("Query is empty after normalization")

    # Step 2: Remove stopwords
    without_stopwords = remove_stopwords(normalized)
    if not without_stopwords:
        logger.warning("Query contains only stopwords, using normalized version")
        without_stopwords = normalized

    # Step 3: Expand synonyms
    with_synonyms = expand_synonyms(without_stopwords)

    # Step 4: Add wildcards
    final_query = add_wildcards(with_synonyms, min_word_length=3)

    logger.info(f"Final FTS query: '{final_query}'")

    return final_query


# ============================================================================
# Utility Functions
# ============================================================================

def get_stopwords() -> Set[str]:
    """
    Get the current set of Russian stopwords.

    Returns:
        Set of stopword strings
    """
    return RUSSIAN_STOPWORDS.copy()


def get_synonyms() -> Dict[str, List[str]]:
    """
    Get the current synonym mappings.

    Returns:
        Dictionary mapping words to their synonym lists
    """
    return SYNONYMS.copy()


def add_custom_stopword(word: str) -> None:
    """
    Add a custom stopword to the global stopwords set.

    Args:
        word: Stopword to add (will be normalized to lowercase)
    """
    normalized_word = word.lower().strip()
    if normalized_word:
        RUSSIAN_STOPWORDS.add(normalized_word)
        logger.info(f"Added custom stopword: '{normalized_word}'")


def add_custom_synonym(word: str, synonyms: List[str]) -> None:
    """
    Add custom synonym mapping.

    Args:
        word: Base word
        synonyms: List of synonym words
    """
    normalized_word = word.lower().strip()
    normalized_synonyms = [s.lower().strip() for s in synonyms]

    if normalized_word and normalized_synonyms:
        SYNONYMS[normalized_word] = normalized_synonyms
        logger.info(f"Added custom synonym: '{normalized_word}' -> {normalized_synonyms}")
