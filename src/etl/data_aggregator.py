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
    3. Price statistics table - price analysis data per resource

    Attributes:
        df: Source DataFrame from ExcelLoader
        rates_df: Aggregated rates DataFrame
        resources_df: Aggregated resources DataFrame
        price_statistics_df: Price statistics DataFrame
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
        self.price_statistics_df: Optional[pd.DataFrame] = None

    def aggregate_rates(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Aggregate construction rates from raw Excel data.

        Groups rows by rate code and creates structured rate records with:
        - Base fields from first row
        - Composition array from "Состав работ" rows
        - Parsed unit measure (number + unit)
        - Full-text search field concatenating all relevant text
        - Phase 1 fields: НР (overhead_rate) and СП (profit_margin)
        - Task 9.2 fields: 13 ГЭСН/ФЕР hierarchy fields

        Args:
            df: Source DataFrame with raw Excel data

        Returns:
            Tuple of (rates_df, resources_df, price_statistics_df)

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
        price_statistics_list = []

        logger.info(f"Processing {len(grouped)} unique rates...")

        with tqdm(total=len(grouped), desc="Aggregating rates") as pbar:
            for rate_code, group in grouped:
                try:
                    rate_record = self._aggregate_single_rate(rate_code, group)
                    if rate_record:
                        rates_list.append(rate_record)

                        # Extract price statistics for each resource in this rate
                        for _, row in group.iterrows():
                            if pd.notna(row.get('Ресурс | Код')):
                                price_stats = self._extract_price_statistics(row)
                                if price_stats:
                                    price_statistics_list.append(price_stats)
                except Exception as e:
                    logger.warning(f"Failed to aggregate rate {rate_code}: {str(e)}")

                pbar.update(1)

        # Create DataFrames
        rates_df = pd.DataFrame(rates_list)
        price_statistics_df = pd.DataFrame(price_statistics_list)

        # Validate aggregated data
        self._validate_rates(rates_df)

        logger.info(f"Successfully aggregated {len(rates_df)} rates")
        logger.debug(f"Extracted {len(price_statistics_list)} price statistics")

        self.rates_df = rates_df
        self.price_statistics_df = price_statistics_df

        return rates_df, self.resources_df if self.resources_df is not None else pd.DataFrame(), price_statistics_df

    def aggregate_resources(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate resources data linked to rates.

        Creates separate DataFrame for resources table with:
        - Resource code and details
        - Link to parent rate via rate_code
        - Resource costs and pricing
        - Phase 1 fields: machinery/labor details

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

        # ========================================================================
        # TASK 9.2 FIX #4: Extract correct rate_short_name from Excel column 16
        # ========================================================================
        # WRONG: 'Расценка | Краткое наименование' (does NOT exist in Excel)
        # CORRECT: 'Расценка | Конечное наименование' (Excel column 16)
        rate_short_name = self._safe_str(first_row.get('Расценка | Конечное наименование', ''))

        # Extract base fields
        rate_full_name = self._safe_str(first_row.get('Расценка | Исходное наименование', ''))

        # Old mapping (kept for backward compatibility in 'category' field)
        section_name_legacy = self._safe_str(first_row.get('Раздел | Имя', ''))

        unit_measure = self._safe_str(first_row.get('Расценка | Ед. изм.', ''))

        # ========================================================================
        # TASK 9.2 P0 FIX #1: Extract 13 ГЭСН/ФЕР hierarchy fields (Excel cols 1-13)
        # ========================================================================
        # Level 1: Category (Категория | Тип) - Excel column 1
        category_type = self._safe_str(first_row.get('Категория | Тип', ''))

        # Level 2: Collection (Сборник | Код, Имя) - Excel columns 2-3
        collection_code = self._safe_str(first_row.get('Сборник | Код', ''))
        collection_name = self._safe_str(first_row.get('Сборник | Имя', ''))

        # Level 3: Department (Отдел | Код, Имя, Тип) - Excel columns 4-6
        department_code = self._safe_str(first_row.get('Отдел | Код', ''))
        department_name = self._safe_str(first_row.get('Отдел | Имя', ''))
        department_type = self._safe_str(first_row.get('Отдел | Тип', ''))

        # Level 4: Section (Раздел | Код, Имя, Тип) - Excel columns 7-9
        section_code = self._safe_str(first_row.get('Раздел | Код', ''))
        section_name = self._safe_str(first_row.get('Раздел | Имя', ''))
        section_type = self._safe_str(first_row.get('Раздел | Тип', ''))

        # Level 5: Subsection (Подраздел | Код, Имя) - Excel columns 10-11
        subsection_code = self._safe_str(first_row.get('Подраздел | Код', ''))
        subsection_name = self._safe_str(first_row.get('Подраздел | Имя', ''))

        # Level 6: Table (Таблица | Код, Имя) - Excel columns 12-13
        table_code = self._safe_str(first_row.get('Таблица | Код', ''))
        table_name = self._safe_str(first_row.get('Таблица | Имя', ''))

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

        # ========================================================================
        # TASK 9.2 P0 FIX #3: Extract aggregated costs from Excel columns 32-34
        # CORRECTED MAPPING (2025-10-20):
        # - Column 32 (Сумма стоимости ресурсов) → resources_cost (not total_cost!)
        # - Column 33 (Сумма стоимости материалов) → materials_cost ✓
        # - Column 34 (Общая стоимость) → total_cost (not resources_cost!)
        # ========================================================================
        # Column 32: Сумма стоимости ресурсов по позиции -> resources_cost
        resources_cost = self._safe_float(first_row.get('Сумма стоимости ресурсов по позиции'))
        if resources_cost is None:
            resources_cost = 0.0

        # Column 33: Сумма стоимости материалов по позиции -> materials_cost
        materials_cost = self._safe_float(first_row.get('Сумма стоимости материалов по позиции'))
        if materials_cost is None:
            materials_cost = 0.0

        # Column 34: Общая стоимость по позиции -> total_cost
        total_cost = self._safe_float(first_row.get('Общая стоимость по позиции'))
        if total_cost is None:
            total_cost = 0.0

        # Create search text (include hierarchy fields for better FTS5 matching)
        search_text = self._create_search_text(
            rate_full_name,
            rate_short_name,
            collection_name,
            department_name,
            section_name,
            subsection_name,
            table_name,
            composition_text
        )

        # Build rate record
        rate_record = {
            'rate_code': str(rate_code),
            'rate_full_name': rate_full_name,
            'rate_short_name': rate_short_name,
            'section_name': section_name_legacy,  # Old field (backward compatibility with 'category')
            'unit_measure': unit_measure,
            'unit_number': unit_number,
            'unit': unit,
            'composition': json.dumps(composition, ensure_ascii=False) if composition else None,
            'search_text': search_text,
            # TASK 9.2: Add aggregated costs
            'total_cost': total_cost,
            'materials_cost': materials_cost,
            'resources_cost': resources_cost,
            # TASK 9.2: Add 13 hierarchy fields
            'category_type': category_type,
            'collection_code': collection_code,
            'collection_name': collection_name,
            'department_code': department_code,
            'department_name': department_name,
            'department_type': department_type,
            'section_code': section_code,
            'section_name_new': section_name,  # New field (will be mapped to section_name in populator)
            'section_type': section_type,
            'subsection_code': subsection_code,
            'subsection_name': subsection_name,
            'table_code': table_code,
            'table_name': table_name
        }

        # Add optional fields if available
        optional_fields = {
            'rate_cost': 'Расценка | Стоимость (руб.)',
            'section_code_legacy': 'Раздел | Код'
        }

        for field_name, col_name in optional_fields.items():
            if col_name in first_row.index:
                value = first_row.get(col_name)
                if pd.notna(value):
                    rate_record[field_name] = value

        # PHASE 1: Extract НР (overhead_rate) and СП (profit_margin)
        # Keep percentages as-is (don't divide by 100)
        overhead_rate = self._safe_float(first_row.get('Обоснование | НР'))
        if overhead_rate is not None:
            rate_record['overhead_rate'] = overhead_rate

        profit_margin = self._safe_float(first_row.get('Обоснование | СП'))
        if profit_margin is not None:
            rate_record['profit_margin'] = profit_margin

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
            text = self._safe_str(row.get('Ресурс | Наименование', ''))

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
        resource_name = self._safe_str(row.get('Ресурс | Наименование', ''))

        # CRITICAL FIX: Ensure resource_name is never empty (NOT NULL constraint in schema)
        # Fallback to resource_code if resource_name is empty
        if not resource_name:
            resource_name = str(resource_code)
            logger.warning(f"Resource {resource_code}: Using resource_code as fallback for empty resource_name")

        # Extract unit (with fallback)
        unit = self._safe_str(row.get('Ресурс | Ед. изм.', ''))
        if not unit:
            unit = 'шт'  # Default fallback for NOT NULL constraint
            logger.debug(f"Resource {resource_code}: Using 'шт' as fallback for empty unit")

        resource_record = {
            'rate_code': str(rate_code),
            'resource_code': str(resource_code),
            'resource_name': resource_name,
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

        # PHASE 1: Extract 7 machinery/labor fields
        # Machinist wage
        machinist_wage = self._safe_float(row.get('Цена | Зарплата машиниста'))
        if machinist_wage is not None:
            resource_record['machinist_wage'] = machinist_wage

        # Machinist labor hours - handle potential "labor_hours/machine_hours" format
        labor_hours_raw = self._safe_str(row.get('Цена | Трудозатраты машиниста, чел.-ч/маш.-ч'))
        if labor_hours_raw:
            if '/' in labor_hours_raw:
                # Split into labor_hours and machine_hours
                parts = labor_hours_raw.split('/')
                if len(parts) == 2:
                    labor_hours = self._safe_float(parts[0].strip())
                    machine_hours = self._safe_float(parts[1].strip())
                    if labor_hours is not None:
                        resource_record['machinist_labor_hours'] = labor_hours
                    if machine_hours is not None:
                        resource_record['machinist_machine_hours'] = machine_hours
            else:
                # Single value - assume it's labor hours
                labor_hours = self._safe_float(labor_hours_raw)
                if labor_hours is not None:
                    resource_record['machinist_labor_hours'] = labor_hours

        # Cost without wages
        cost_without_wages = self._safe_float(row.get('Цена | Стоимость без зарплаты'))
        if cost_without_wages is not None:
            resource_record['cost_without_wages'] = cost_without_wages

        # Relocation included - convert to 0/1
        relocation_raw = row.get('Цена | Перебазировка учтена')
        if pd.notna(relocation_raw):
            relocation_included = self._convert_to_bool_int(relocation_raw)
            resource_record['relocation_included'] = relocation_included

        # Personnel code
        personnel_code = self._safe_str(row.get('Персонал | Код машиниста'))
        if personnel_code:
            resource_record['personnel_code'] = personnel_code

        # Machinist grade
        machinist_grade = self._safe_str(row.get('Персонал | Разряд машиниста'))
        if machinist_grade:
            resource_record['machinist_grade'] = machinist_grade

        return resource_record

    def _extract_price_statistics(self, row: pd.Series) -> Optional[Dict[str, Any]]:
        """
        Extract price statistics from a resource row.

        Extracts 9 price analysis fields per resource:
        - Min/max/mean/median current prices
        - Unit match flag
        - Material and position costs

        Args:
            row: Source row from DataFrame

        Returns:
            Dict with price statistics or None if extraction fails
        """
        rate_code = row.get('Расценка | Код')
        resource_code = row.get('Ресурс | Код')

        if pd.isna(rate_code) or pd.isna(resource_code):
            return None

        price_stats = {
            'rate_code': str(rate_code),
            'resource_code': str(resource_code)
        }

        # Extract price statistics fields
        # Current price min/max/mean/median
        current_price_min = self._safe_float(row.get('Прайс | АбстРесурс | Сметная цена текущая_min'))
        if current_price_min is not None:
            price_stats['current_price_min'] = current_price_min
        else:
            price_stats['current_price_min'] = 0.0

        current_price_max = self._safe_float(row.get('Прайс | АбстРесурс | Сметная цена текущая_max'))
        if current_price_max is not None:
            price_stats['current_price_max'] = current_price_max
        else:
            price_stats['current_price_max'] = 0.0

        current_price_mean = self._safe_float(row.get('Прайс | АбстРесурс | Сметная цена текущая_mean'))
        if current_price_mean is not None:
            price_stats['current_price_mean'] = current_price_mean
        else:
            price_stats['current_price_mean'] = 0.0

        current_price_median = self._safe_float(row.get('Прайс | АбстРесурс | Сметная цена текущая_median'))
        if current_price_median is not None:
            price_stats['current_price_median'] = current_price_median
        else:
            price_stats['current_price_median'] = 0.0

        # Unit match flag - convert to 0/1
        unit_match_raw = row.get('Совпадение единицы измерений расценки и цены')
        if pd.notna(unit_match_raw):
            price_stats['unit_match'] = self._convert_to_bool_int(unit_match_raw)
        else:
            price_stats['unit_match'] = 0

        # Material resource cost
        material_resource_cost = self._safe_float(row.get('Материалы Ресурс | Стоимость (руб.)'))
        if material_resource_cost is not None:
            price_stats['material_resource_cost'] = material_resource_cost
        else:
            price_stats['material_resource_cost'] = 0.0

        # Total resource cost
        total_resource_cost = self._safe_float(row.get('Сумма стоимости ресурсов по позиции'))
        if total_resource_cost is not None:
            price_stats['total_resource_cost'] = total_resource_cost
        else:
            price_stats['total_resource_cost'] = 0.0

        # Total material cost
        total_material_cost = self._safe_float(row.get('Сумма стоимости материалов по позиции'))
        if total_material_cost is not None:
            price_stats['total_material_cost'] = total_material_cost
        else:
            price_stats['total_material_cost'] = 0.0

        # Total position cost
        total_position_cost = self._safe_float(row.get('Общая стоимость по позиции'))
        if total_position_cost is not None:
            price_stats['total_position_cost'] = total_position_cost
        else:
            price_stats['total_position_cost'] = 0.0

        return price_stats

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

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """
        Safely convert value to float, handling NaN, None, and invalid values.

        Args:
            value: Value to convert

        Returns:
            Float value or None if conversion fails
        """
        if value is None or pd.isna(value):
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _convert_to_bool_int(value: Any) -> int:
        """
        Convert boolean-like value to 0 or 1.

        Handles: "Да"/"Yes"/True/1 -> 1, everything else -> 0

        Args:
            value: Value to convert

        Returns:
            0 or 1
        """
        if value is None or pd.isna(value):
            return 0

        if isinstance(value, bool):
            return 1 if value else 0

        if isinstance(value, (int, float)):
            return 1 if value != 0 else 0

        # String comparison (case-insensitive)
        str_value = str(value).strip().lower()
        if str_value in ('да', 'yes', 'true', '1', '+'):
            return 1

        return 0

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about aggregated data.

        Returns:
            Dict with rates, resources, and price statistics
        """
        stats = {}

        if self.rates_df is not None:
            stats['rates'] = {
                'total': len(self.rates_df),
                'rates_with_composition': self.rates_df['composition'].notna().sum(),
                'rates_with_unit_number': self.rates_df['unit_number'].notna().sum(),
                'unique_sections': self.rates_df['section_name'].nunique() if 'section_name' in self.rates_df.columns else 0,
                'with_overhead_rate': self.rates_df['overhead_rate'].notna().sum() if 'overhead_rate' in self.rates_df.columns else 0,
                'with_profit_margin': self.rates_df['profit_margin'].notna().sum() if 'profit_margin' in self.rates_df.columns else 0,
                # TASK 9.2: Add hierarchy stats
                'with_collection_code': self.rates_df['collection_code'].notna().sum() if 'collection_code' in self.rates_df.columns else 0,
                'with_department_code': self.rates_df['department_code'].notna().sum() if 'department_code' in self.rates_df.columns else 0,
                'with_section_code': self.rates_df['section_code'].notna().sum() if 'section_code' in self.rates_df.columns else 0,
                'with_total_cost': (self.rates_df['total_cost'] > 0).sum() if 'total_cost' in self.rates_df.columns else 0
            }

        if self.resources_df is not None:
            stats['resources'] = {
                'total': len(self.resources_df),
                'unique_resources': self.resources_df['resource_code'].nunique(),
                'linked_rates': self.resources_df['rate_code'].nunique(),
                'with_machinist_wage': self.resources_df['machinist_wage'].notna().sum() if 'machinist_wage' in self.resources_df.columns else 0,
                'with_personnel_code': self.resources_df['personnel_code'].notna().sum() if 'personnel_code' in self.resources_df.columns else 0
            }

        if self.price_statistics_df is not None:
            stats['price_statistics'] = {
                'total': len(self.price_statistics_df),
                'unique_resources': self.price_statistics_df['resource_code'].nunique() if len(self.price_statistics_df) > 0 else 0,
                'with_price_data': (self.price_statistics_df['current_price_median'] > 0).sum() if len(self.price_statistics_df) > 0 else 0
            }

        logger.info(f"Aggregation statistics: {stats}")
        return stats
