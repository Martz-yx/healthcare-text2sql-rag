# Healthcare Data Warehouse - Technical Implementation

This folder contains the actual dbt project code used to build the Data Warehouse.

## Running the Project
1. Install dependencies: `dbt deps`
2. Build the project: `dbt build`

## Architecture Rules
- **Staging (`stg_`)**: Base tables directly mapped from source. No heavy joins. Renaming and casting only.
- **Intermediate (`int_`)**: Heavy business logic and metric calculation.
- **Marts (`mart_`)**: The final, presentation-ready tables consumed by BI and AI RAG models. Always strictly materialized as `table` or `incremental`.

## Custom Macros
- `limit_data_in_dev`: Used to truncate datasets automatically when developing locally to save compute costs.

## Testing
To run the automated data quality tests, including custom singular tests like `assert_fechas_internacion_validas`, execute:
```bash
dbt test
```
