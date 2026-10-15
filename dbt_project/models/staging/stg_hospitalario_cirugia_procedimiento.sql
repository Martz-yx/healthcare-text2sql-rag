SELECT
    *,
    CASE estado
        WHEN 'A' THEN 'Finalizado'
        WHEN 'P' THEN 'Pendiente'
        WHEN 'D' THEN 'Eliminado'
        ELSE estado
    END AS estado_desc
FROM {{ source('his', 'hospitalario_cirugia_procedimiento') }}