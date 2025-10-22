"""
ETL (Extract, Transform, Load) package for Construction Estimator

This package handles loading data from Excel files and populating the SQLite database.

Modules:
    excel_loader: Loads and validates Excel files
    data_aggregator: Aggregates and transforms data
    db_populator: Populates SQLite database

Usage:
    python -m src.etl.excel_to_sqlite
"""

__version__ = "1.0.0"
