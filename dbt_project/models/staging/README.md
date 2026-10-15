# Staging Layer (`staging/`)

The staging layer manages and normalizes raw transactional data.

In this layer, a 1:1 relationship with the raw tables from the source database is maintained, while applying standardizations:
- **Renaming**: Converting source columns into standardized formats (e.g., in `stg_paciente` and `stg_usuario`).
- **Type Casting**: Ensuring dates are timestamps, numbers are cast correctly, and string lengths are consistent.
- **Light Transformation**: Replacing NULLs with defaults where appropriate, without performing complex joins or aggregations.

This layer centralizes foundational logic. If the source database schema changes, updates are isolated to the staging models, shielding downstream models from structural changes.
