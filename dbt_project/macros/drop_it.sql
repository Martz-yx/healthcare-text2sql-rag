{% macro drop_it() %}
  {% do run_query('drop table if exists dbt_analytics.mart_medicamentos_recetados cascade') %}
{% endmacro %}
