SELECT
    *,
    CASE tipo_evolucion
        WHEN 'EVO' THEN 'Evolución normal'
        WHEN 'SUS' THEN 'Suspensión de medicamento'
        ELSE tipo_evolucion::text
    END AS tipo_evolucion_desc,
    CASE estado
        WHEN 'A' THEN 'Finalizado'
        WHEN 'P' THEN 'Pendiente'
        WHEN 'D' THEN 'Eliminado'
        ELSE estado
    END AS estado_desc
FROM {{ source('his', 'hospitalario_evolucion') }}