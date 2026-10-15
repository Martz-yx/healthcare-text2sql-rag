# Models Directory

This directory contains the core data transformations for the Data Warehouse, structured according to dbt best practices. Models are separated into three distinct layers to ensure modularity, reusability, and ease of maintenance:

1. **`staging/`**: Cleans, casts, and normalizes raw tables from the HIS database.
2. **`intermediate/`**: Combines staging tables and calculates complex business logic.
3. **`marts/`**: Domain-specific, highly optimized tables and materialized views built for end-consumers.

This layered approach ensures that the final Data Marts are built on standardized and tested building blocks.
