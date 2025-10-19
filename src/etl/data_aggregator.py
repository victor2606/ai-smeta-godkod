"""
Data Aggregator for Construction Rates ETL Pipeline
Aggregates raw Excel data into structured rates and resources tables.
"""

import pandas as pd
import logging
import re
import json
from typing import Dict, List, Any, Optional, Tuple
from tqdm import tqdm


logger = logging.getLogger(__name__)


class DataAggregator:
    """
    Aggregates construction rate data from raw Excel format into structured tables.

    Transforms row-based Excel data into:
    1. Rates table - aggregated rate information with composition
    2. Resources table - linked resource details for each rate

    Attributes:
        df: Source DataFrame from ExcelLoader
        rates_df: Aggregated rates DataFrame
        resources_df: Aggregated resources DataFrame
    """

    # Row types to extract as composition
    COMPOSITION_ROW_TYPES = ['Состав работ']

    # Required fields for rate validation
    REQUIRED_RATE_FIELDS = [
        'rate_code',
        'rate_full_name',
        'unit'
    ]

    def __init__(self, df: pd.DataFrame):
        """
        Initialize aggregator with source DataFrame.

        Args:
            df: Source DataFrame from ExcelLoader
        """
        self.df = df
        self.rates_df: Optional[pd.DataFrame] = None
        self.resources_df: Optional[pd.DataFrame] = None

    def aggregate_rates(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate construction rates from raw Excel data.

        Groups rows by rate code and creates structured rate records with:
        - Base fields from first row
        - Composition array from "Состав работ" rows
        - Parsed unit measure (number + unit)
        - Full-text search field concatenating all relevant text

        Args:
            df: Source DataFrame with raw Excel data

        Returns:
            DataFrame with aggregated rates

        Raises:
            ValueError: If required columns missing or validation fails
        """
        logger.info("Starting rate aggregation...")

        # Validate required columns
        required_cols = [
            'Расценка | Код',
            'Расценка | Исходное наименование',
            'Расценка | Ед. изм.',
            'Тип строки'
        ]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Group by rate code
        grouped = df.groupby('Расценка | Код')
        rates_list = []

        logger.info(f"Processing {len(grouped)} unique rates...")

        with tqdm(total=len(grouped), desc="Aggregating rates") as pbar:
            for rate_code, group in grouped:
                try:
                    rate_record = self._aggregate_single_rate(rate_code, group)
                    if rate_record:
                        rates_list.append(rate_record)
                except Exception as e:
                    logger.warning(f"Failed to aggregate rate {rate_code}: {str(e)}")

                pbar.update(1)

        # Create DataFrame
        rates_df = pd.DataFrame(rates_list)

        # Validate aggregated data
        self._validate_rates(rates_df)

        logger.info(f"Successfully aggregated {len(rates_df)} rates")
        self.rates_df = rates_df

        return rates_df

    def aggregate_resources(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate resources data linked to rates.

        Creates separate DataFrame for resources table with:
        - Resource code and details
        - Link to parent rate via rate_code
        - Resource costs and pricing

        Args:
            df: Source DataFrame with raw Excel data

        Returns:
            DataFrame with aggregated resources

        Raises:
            ValueError: If required columns missing
        """
        logger.info("Starting resource aggregation...")

        # Validate required columns
        required_cols = [
            'Расценка | Код',
            'Ресурс | Код'
        ]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Filter rows with resource codes
        resources_df = df[df['Ресурс | Код'].notna()].copy()

        if len(resources_df) == 0:
            logger.warning("No resources found in source data")
            self.resources_df = pd.DataFrame()
            return self.resources_df

        # Extract resource fields
        resources_list = []

        logger.info(f"Processing {len(resources_df)} resource rows...")

        with tqdm(total=len(resources_df), desc="Aggregating resources") as pbar:
            for _, row in resources_df.iterrows():
                try:
                    resource_record = self._extract_resource_record(row)
                    if resource_record:
                        resources_list.append(resource_record)
                except Exception as e:
                    logger.warning(f"Failed to extract resource: {str(e)}")

                pbar.update(1)

        # Create DataFrame
        self.resources_df = pd.DataFrame(resources_list)

        logger.info(f"Successfully aggregated {len(self.resources_df)} resources")

        return self.resources_df

    def _aggregate_single_rate(self, rate_code: str, group: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Aggregate a single rate from its group of rows.

        Args:
            rate_code: Rate code identifier
            group: DataFrame with all rows for this rate

        Returns:
            Dict with aggregated rate data or None if aggregation fails
        """
        # Get first row for base fields
        first_row = group.iloc[0]

        # Extract base fields
        rate_full_name = self._safe_str(first_row.get('Расценка | Исходное наименование', ''))
        rate_short_name = self._safe_str(first_row.get('Расценка | Краткое наименование', ''))
        section_name = self._safe_str(first_row.get('Раздел | Наименование', ''))
        unit_measure = self._safe_str(first_row.get('Расценка | Ед. изм.', ''))

        # CRITICAL FIX: Ensure rate_full_name is never empty (NOT NULL constraint in schema)
        # Fallback order: rate_full_name -> rate_short_name -> rate_code
        if not rate_full_name:
            if rate_short_name:
                rate_full_name = rate_short_name
                logger.debug(f"Rate {rate_code}: Using rate_short_name as fallback for empty rate_full_name")
            else:
                rate_full_name = str(rate_code)
                logger.warning(f"Rate {rate_code}: Using rate_code as fallback for empty rate_full_name")

        # Parse unit measure
        unit_number, unit = self._parse_unit_measure(unit_measure)

        # CRITICAL FIX: Ensure unit is never empty (NOT NULL constraint in schema)
        # Fallback to 'шт' (piece) if no unit found
        if not unit:
            unit = 'шт'
            logger.debug(f"Rate {rate_code}: Using 'шт' as fallback for empty unit")

        # Extract composition
        composition = self._extract_composition(group)
        composition_text = ' '.join([c.get('text', '') for c in composition])

        # Create search text
        search_text = self._create_search_text(
            rate_full_name,
            rate_short_name,
            section_name,
            composition_text
        )

        # Build rate record
        rate_record = {
            'rate_code': str(rate_code),
            'rate_full_name': rate_full_name,
            'rate_short_name': rate_short_name,
            'section_name': section_name,
            'unit_measure': unit_measure,
            'unit_number': unit_number,
            'unit': unit,
            'composition': json.dumps(composition, ensure_ascii=False) if composition else None,
            'search_text': search_text
        }

        # Add optional fields if available
        optional_fields = {
            'rate_cost': 'Расценка | Стоимость (руб.)',
            'section_code': 'Раздел | Код',
            'chapter_name': 'Глава | Наименование',
            'chapter_code': 'Глава | Код'
        }

        for field_name, col_name in optional_fields.items():
            if col_name in first_row.index:
                value = first_row.get(col_name)
                if pd.notna(value):
                    rate_record[field_name] = value

        return rate_record

    def _extract_composition(self, group: pd.DataFrame) -> List[Dict[str, str]]:
        """
        Extract composition rows from rate group.

        Args:
            group: DataFrame with all rows for a rate

        Returns:
            List of composition dictionaries
        """
        composition = []

        # Filter composition rows
        comp_rows = group[group['Тип строки'].isin(self.COMPOSITION_ROW_TYPES)]

        for _, row in comp_rows.iterrows():
            comp_item = {}

            # Extract composition text
            text = self._safe_str(row.get('Ресурс | Исходное наименование', ''))
            if not text:
                text = self._safe_str(row.get('Ресурс | Краткое наименование', ''))

            if text:
                comp_item['text'] = text

                # Add resource code if available
                res_code = row.get('Ресурс | Код')
                if pd.notna(res_code):
                    comp_item['resource_code'] = str(res_code)

                composition.append(comp_item)

        return composition

    def _parse_unit_measure(self, unit_measure: str) -> Tuple[Optional[float], Optional[str]]:
        """
        Parse unit measure string to extract number and unit.

        Examples:
            "100 м2" -> (100.0, "м2")
            "1 м3" -> (1.0, "м3")
            "т" -> (None, "т")

        Args:
            unit_measure: Unit measure string

        Returns:
            Tuple of (number, unit) or (None, unit) if no number found
        """
        if not unit_measure or pd.isna(unit_measure):
            return None, None

        # Try to match pattern: number + space + unit
        match = re.match(r'^(\d+(?:\.\d+)?)\s*(.+)$', str(unit_measure).strip())

        if match:
            try:
                number = float(match.group(1))
                unit = match.group(2).strip()
                return number, unit
            except ValueError:
                pass

        # If no number found, return just the unit
        return None, str(unit_measure).strip()

    def _create_search_text(self, *texts: str) -> str:
        """
        Create full-text search field from multiple text sources.

        Args:
            *texts: Variable number of text strings to concatenate

        Returns:
            Concatenated and cleaned search text
        """
        # Filter out empty/None values and join
        valid_texts = [str(t).strip() for t in texts if t and pd.notna(t) and str(t).strip()]
        return ' '.join(valid_texts)

    def _extract_resource_record(self, row: pd.Series) -> Optional[Dict[str, Any]]:
        """
        Extract resource record from a single row.

        Args:
            row: Source row from DataFrame

        Returns:
            Dict with resource data or None if extraction fails
        """
        rate_code = row.get('Расценка | Код')
        resource_code = row.get('Ресурс | Код')

        if pd.isna(rate_code) or pd.isna(resource_code):
            return None

        # Extract base fields
        resource_name = self._safe_str(row.get('Ресурс | Исходное наименование', ''))
        resource_short_name = self._safe_str(row.get('Ресурс | Краткое наименование', ''))

        # CRITICAL FIX: Ensure resource_name is never empty (NOT NULL constraint in schema)
        # Fallback order: resource_name -> resource_short_name -> resource_code
        if not resource_name:
            if resource_short_name:
                resource_name = resource_short_name
                logger.debug(f"Resource {resource_code}: Using resource_short_name as fallback")
            else:
                resource_name = str(resource_code)
                logger.warning(f"Resource {resource_code}: Using resource_code as fallback")

        # Extract unit (with fallback)
        unit = self._safe_str(row.get('Ресурс | Ед. изм.', ''))
        if not unit:
            unit = 'шт'  # Default fallback for NOT NULL constraint
            logger.debug(f"Resource {resource_code}: Using 'шт' as fallback for empty unit")

        resource_record = {
            'rate_code': str(rate_code),
            'resource_code': str(resource_code),
            'resource_name': resource_name,
            'resource_short_name': resource_short_name,
            'row_type': self._safe_str(row.get('Тип строки', '')),
            'unit': unit
        }

        # Add numeric fields
        numeric_fields = {
            'resource_cost': 'Ресурс | Стоимость (руб.)',
            'resource_price_median': 'Прайс | АбстРесурс | Сметная цена текущая_median',
            'resource_quantity': 'Ресурс | Количество'
        }

        for field_name, col_name in numeric_fields.items():
            if col_name in row.index:
                value = row.get(col_name)
                if pd.notna(value):
                    try:
                        resource_record[field_name] = float(value)
                    except (ValueError, TypeError):
                        logger.debug(f"Could not convert {col_name} to float: {value}")

        return resource_record

    def _validate_rates(self, rates_df: pd.DataFrame) -> None:
        """
        Validate aggregated rates DataFrame.

        Args:
            rates_df: Aggregated rates DataFrame

        Raises:
            ValueError: If validation fails
        """
        if len(rates_df) == 0:
            raise ValueError("No rates were aggregated")

        # Check required fields
        missing = [f for f in self.REQUIRED_RATE_FIELDS if f not in rates_df.columns]
        if missing:
            raise ValueError(f"Missing required rate fields: {missing}")

        # Check for empty required fields
        for field in self.REQUIRED_RATE_FIELDS:
            empty_count = rates_df[field].isna().sum()
            if empty_count > 0:
                logger.warning(f"Field '{field}' has {empty_count} empty values")

        # Log statistics
        stats = {
            'total_rates': len(rates_df),
            'rates_with_composition': rates_df['composition'].notna().sum(),
            'rates_with_unit_number': rates_df['unit_number'].notna().sum(),
            'unique_units': rates_df['unit'].nunique()
        }
        logger.info(f"Validation stats: {stats}")

    @staticmethod
    def _safe_str(value: Any) -> str:
        """
        Safely convert value to string, handling NaN and None.

        Args:
            value: Value to convert

        Returns:
            String representation or empty string
        """
        if value is None or pd.isna(value):
            return ''
        return str(value).strip()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about aggregated data.

        Returns:
            Dict with rates and resources statistics
        """
        stats = {}

        if self.rates_df is not None:
            stats['rates'] = {
                'total': len(self.rates_df),
                'with_composition': self.rates_df['composition'].notna().sum(),
                'with_unit_number': self.rates_df['unit_number'].notna().sum(),
                'unique_sections': self.rates_df['section_name'].nunique() if 'section_name' in self.rates_df.columns else 0
            }

        if self.resources_df is not None:
            stats['resources'] = {
                'total': len(self.resources_df),
                'unique_resources': self.resources_df['resource_code'].nunique(),
                'linked_rates': self.resources_df['rate_code'].nunique()
            }

        logger.info(f"Aggregation statistics: {stats}")
        return stats
