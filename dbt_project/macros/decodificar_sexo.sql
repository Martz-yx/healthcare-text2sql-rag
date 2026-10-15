-- Macro: Decodificar sexo del paciente.
-- Uso: {{ decodificar_sexo('p') }} → CASE p.sexo WHEN '1' THEN 'Femenino' ...
{% macro decodificar_sexo(alias) %}
    CASE {{ alias }}.sexo
        WHEN '1' THEN 'Femenino'
        WHEN '2' THEN 'Masculino'
        ELSE 'No especificado'
    END
{% endmacro %}
