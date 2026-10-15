-- Overrides the default dbt create_schema macro.
-- This prevents dbt from running CREATE SCHEMA IF NOT EXISTS,
-- which fails with 'permission denied for database' because
-- the dbt service user lacks database-level CREATE privileges,
-- even though the schema dbt_analytics already exists and is writable.

{% macro postgres__create_schema(relation) %}
  {{ log("Skipping schema creation for " ~ relation, info=True) }}
  {%- call statement('create_schema') -%}
    select 1
  {%- endcall -%}
{% endmacro %}
