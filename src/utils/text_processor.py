"""
Text Processing Utilities for Construction Rate Data
Provides helper functions for parsing and cleaning Russian construction data.
"""

import re
import logging
from typing import Tuple, Optional


logger = logging.getLogger(__name__)


# Import pandas for NaN checking (optional dependency)
try:
    import pandas as pd
except ImportError:
    # Create dummy isna function if pandas not available
    class pd:
        @staticmethod
        def isna(value):
            return value is None


def parse_unit_measure(text: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Parse unit measure string to extract quantity and unit.

    Args:
        text: Input string like "100 м2", "10 шт", "1 т"

    Returns:
        Tuple of (quantity, unit) or (None, None) if cannot parse

    Examples:
        >>> parse_unit_measure("100 м2")
        (100.0, "м2")
        >>> parse_unit_measure("10 шт")
        (10.0, "шт")
        >>> parse_unit_measure("1 т")
        (1.0, "т")
        >>> parse_unit_measure("invalid")
        (None, None)
    """
    if text is None or (isinstance(text, float) and pd.isna(text)):
        logger.warning("Received None or NaN in parse_unit_measure")
        return (None, None)

    text = str(text).strip()

    if not text:
        return (None, None)

    # Regex pattern: optional number (int or float) followed by optional space and unit
    # Supports Russian units: м, м2, м3, шт, т, кг, л, etc.
    pattern = r'^([\d.,]+)\s*([а-яА-Яa-zA-Z0-9]+)$'

    match = re.match(pattern, text)

    if match:
        try:
            # Replace comma with dot for float parsing
            quantity_str = match.group(1).replace(',', '.')
            quantity = float(quantity_str)
            unit = match.group(2)
            return (quantity, unit)
        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse quantity from '{text}': {e}")
            return (None, None)

    logger.warning(f"Could not parse unit measure from: '{text}'")
    return (None, None)


def clean_text(text: str) -> str:
    """
    Clean and normalize text by removing extra whitespace.

    Args:
        text: Input text string

    Returns:
        Cleaned text with normalized whitespace

    Examples:
        >>> clean_text("  hello   world  ")
        "hello world"
        >>> clean_text("multiple   spaces")
        "multiple spaces"
        >>> clean_text(None)
        ""
    """
    # Handle None and NaN
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""

    # Convert to string
    text = str(text)

    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)

    # Strip leading and trailing whitespace
    text = text.strip()

    return text


def build_search_text(*fields: str) -> str:
    """
    Concatenate fields for full-text search (FTS).

    Args:
        *fields: Variable number of text fields to concatenate

    Returns:
        Lowercase, cleaned, concatenated search text

    Examples:
        >>> build_search_text("Монтаж", "конструкций", None, "металлических")
        "монтаж конструкций металлических"
        >>> build_search_text("  Test  ", "  Value  ")
        "test value"
        >>> build_search_text(None, "", "Valid")
        "valid"
    """
    # Filter out None and empty strings
    valid_fields = []

    for field in fields:
        if field is not None:
            # Handle NaN
            if isinstance(field, float) and pd.isna(field):
                continue

            # Clean and add non-empty fields
            cleaned = clean_text(field)
            if cleaned:
                valid_fields.append(cleaned)

    # Join with space, clean again, and lowercase
    result = ' '.join(valid_fields)
    result = clean_text(result)
    result = result.lower()

    return result
