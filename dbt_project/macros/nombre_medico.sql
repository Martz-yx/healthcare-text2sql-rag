-- Macro: Construir nombre completo de médico/usuario.
-- Uso: {{ nombre_medico('u') }} → u.nombres || ' ' || u.apellidos
{% macro nombre_medico(alias) %}
    {{ alias }}.nombres || ' ' || {{ alias }}.apellidos
{% endmacro %}
