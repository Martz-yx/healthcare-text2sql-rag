-- Macro: Construir nombre completo de paciente.
-- Uso: {{ nombre_paciente('p') }} → CONCAT(TRIM(p.primer_nombre), ' ', TRIM(p.primer_apellido))
{% macro nombre_paciente(alias) %}
    CONCAT(TRIM({{ alias }}.primer_nombre), ' ', TRIM({{ alias }}.primer_apellido))
{% endmacro %}
