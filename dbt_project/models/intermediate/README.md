# Intermediate Layer (`intermediate/`)

The intermediate layer contains the core business logic.

Logic is modularized into intermediate models rather than being duplicated in Data Marts. For example:
- `int_diagnosticos_top_historico`: Pre-calculates historical aggregations of diagnoses.
- `int_totales_consultas_hoy`: Aggregates daily consultation metrics.

These intermediate tables can be joined by multiple downstream Data Marts, maintaining a DRY (Don't Repeat Yourself) codebase and facilitating the debugging of complex calculations.
