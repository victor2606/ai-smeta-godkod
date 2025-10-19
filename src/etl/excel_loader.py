"""
Excel Loader for Construction Rates Data
Reads and validates Excel files with construction rate schedules.
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, Any
from tqdm import tqdm


logger = logging.getLogger(__name__)


class ExcelLoader:
    """
    Loads and validates Excel files containing construction rate data.

    Attributes:
        file_path: Path to Excel file
        df: Loaded DataFrame
    """

    # Required columns that must exist in Excel
    REQUIRED_COLUMNS = [
        'Расценка | Код',
        'Расценка | Исходное наименование',
        'Расценка | Ед. изм.',
        'Тип строки',
        'Ресурс | Код',
        'Ресурс | Стоимость (руб.)',
        'Прайс | АбстРесурс | Сметная цена текущая_median'
    ]

    # Columns that cannot have NaN values
    CRITICAL_COLUMNS = ['Расценка | Код', 'Тип строки']

    def __init__(self, file_path: str):
        """Initialize with file path."""
        self.file_path = Path(file_path)
        self.df: pd.DataFrame = None

    def load(self) -> pd.DataFrame:
        """
        Load Excel file with progress bar.

        Returns:
            Loaded DataFrame

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file cannot be read
        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        logger.info(f"Loading Excel file: {self.file_path}")

        try:
            # Load with tqdm progress
            with tqdm(total=1, desc="Loading Excel") as pbar:
                self.df = pd.read_excel(self.file_path, engine='openpyxl')
                pbar.update(1)

            logger.info(f"Loaded {len(self.df)} rows, {len(self.df.columns)} columns")
            return self.df

        except Exception as e:
            raise ValueError(f"Failed to load Excel: {str(e)}")

    def validate(self) -> bool:
        """
        Validate loaded data.

        Returns:
            True if valid

        Raises:
            ValueError: If validation fails
        """
        if self.df is None:
            raise ValueError("No data loaded. Call load() first.")

        # Check required columns
        missing = [col for col in self.REQUIRED_COLUMNS if col not in self.df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Check data types
        if not pd.api.types.is_numeric_dtype(self.df['Ресурс | Стоимость (руб.)']):
            logger.warning("Converting 'Ресурс | Стоимость (руб.)' to numeric")
            self.df['Ресурс | Стоимость (руб.)'] = pd.to_numeric(
                self.df['Ресурс | Стоимость (руб.)'], errors='coerce'
            )

        # Check critical NaN values
        for col in self.CRITICAL_COLUMNS:
            nan_count = self.df[col].isna().sum()
            if nan_count > 0:
                raise ValueError(f"Column '{col}' has {nan_count} NaN values")

        logger.info("Validation passed")
        return True

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about loaded data.

        Returns:
            Dict with total_rows, unique_rates, row_types
        """
        if self.df is None:
            raise ValueError("No data loaded. Call load() first.")

        stats = {
            'total_rows': len(self.df),
            'unique_rates': self.df['Расценка | Код'].nunique(),
            'row_types': self.df['Тип строки'].value_counts().to_dict()
        }

        logger.info(f"Statistics: {stats}")
        return stats
