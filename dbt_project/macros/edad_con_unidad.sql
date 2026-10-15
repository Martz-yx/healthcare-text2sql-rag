-- Macro: Decodificar edad con unidad.
-- Uso: {{ edad_con_unidad('ha') }} → ha.edad_paciente || ' ' || CASE ha.tipo_edad ...
{% macro edad_con_unidad(alias) %}
    {{ alias }}.edad_paciente || ' ' ||
    CASE {{ alias }}.tipo_edad
        WHEN 1 THEN 'año(s)'
        WHEN 2 THEN 'mes(es)'
        WHEN 3 THEN 'día(s)'
        WHEN 4 THEN 'hora(s)'
        WHEN 5 THEN 'minuto(s)'
        ELSE 'año(s)'
    END
{% endmacro %}
