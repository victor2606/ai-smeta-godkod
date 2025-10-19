"""
Resource Type Classifier Utility
Classifies construction resources based on row type and resource codes.
"""

from typing import Optional


def classify_resource_type(
    row_type: str,
    resource_code: str,
    resource_name: str
) -> str:
    """
    Classify resource type based on row type and resource identifiers.

    Classification logic:
    - Row type 'Состав работ' -> 'labor'
    - Row type 'Ресурс' -> classified by resource_code:
        - Starts with 'M' -> 'material'
        - Starts with '1-' -> 'machinery'
        - Default -> 'equipment'
    - All other row types -> 'equipment'

    Args:
        row_type: Type of Excel row ('Расценка', 'Ресурс', 'Состав работ')
        resource_code: Resource code identifier (e.g., 'M123', '1-001')
        resource_name: Resource name/description (currently unused, reserved for future logic)

    Returns:
        Resource type as one of: 'material', 'labor', 'machinery', 'equipment'

    Examples:
        >>> classify_resource_type('Состав работ', 'R001', 'Монтажник')
        'labor'

        >>> classify_resource_type('Ресурс', 'M123', 'Цемент')
        'material'

        >>> classify_resource_type('Ресурс', '1-001', 'Экскаватор')
        'machinery'

        >>> classify_resource_type('Ресурс', 'E456', 'Инструмент')
        'equipment'

        >>> classify_resource_type('Расценка', '', '')
        'equipment'

        >>> classify_resource_type(None, None, None)
        'equipment'
    """
    # Handle None and empty values
    safe_row_type = _safe_str(row_type)
    safe_resource_code = _safe_str(resource_code)

    # Classification logic
    if safe_row_type == 'Состав работ':
        return 'labor'

    if safe_row_type == 'Ресурс':
        # Classify by resource code prefix
        if safe_resource_code.startswith('M'):
            return 'material'
        elif safe_resource_code.startswith('1-'):
            return 'machinery'
        else:
            return 'equipment'

    # Default fallback for all other row types
    return 'equipment'


def _safe_str(value: Optional[str]) -> str:
    """
    Safely convert value to string, handling None and empty values.

    Args:
        value: Value to convert

    Returns:
        String representation or empty string
    """
    if value is None or value == '':
        return ''
    return str(value).strip()
