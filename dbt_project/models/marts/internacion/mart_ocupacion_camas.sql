{{ config(materialized='view') }}

-- mart_ocupacion_camas: Estado actual básico de ocupación de camas (súper ligero).
-- Solo incluye servicio y estado. No incluye piso, sala ni edificio.
-- Útil para preguntas generales como "¿cuántas camas libres hay en Urgencias?"

SELECT
    c.codigo_establecimiento,
    est.nombre AS hospital,
    c.servicio,
    c.nombre_cama AS cama,
    c.tipo_cama,
    c.estado_cama AS estado,
    c.asignacion_actual
FROM {{ ref('stg_cama') }} c
LEFT JOIN {{ ref('stg_establecimiento') }} est
    ON c.codigo_establecimiento = est.codigo_establecimiento
WHERE c.cama_activa = true
