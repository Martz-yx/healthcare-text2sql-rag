SELECT
    *,
    CASE estado
        WHEN 'Completo' THEN 'Completo'
        WHEN 'En Proceso' THEN 'En proceso'
        WHEN 'Eliminado' THEN 'Eliminado'
        ELSE COALESCE(estado, 'No especificado')
    END AS estado_desc
FROM {{ source('his', 'consulta_medicamento') }}