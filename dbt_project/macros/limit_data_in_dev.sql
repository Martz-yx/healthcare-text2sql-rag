{% macro limit_data_in_dev(column_name, dev_days_of_data=3) %}
{% if target.name == 'dev' %}
where {{ column_name }} >= current_date - interval '{{ dev_days_of_data }} days'
{% endif %}
{% endmacro %}
