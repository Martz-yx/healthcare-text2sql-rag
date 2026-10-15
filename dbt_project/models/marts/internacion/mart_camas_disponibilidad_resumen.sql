{{ config(materialized='view') }}

-- mart_camas_disponibilidad_resumen: Resumen agregado de camas por hospital, servicio y estado.
-- Permite a la IA responder preguntas rápidamente como "¿Cuántas camas disponibles hay en Urgencias?".

SELECT
    c.codigo_establecimiento,
    est.nombre AS hospital,
    c.servicio,
    c.estado_cama AS estado,
    COUNT(*) AS total_camas
FROM {{ ref('stg_cama') }} c
LEFT JOIN {{ ref('stg_establecimiento') }} est
    ON c.codigo_establecimiento = est.codigo_establecimiento
WHERE c.cama_activa = true
GROUP BY
    c.codigo_establecimiento,
    est.nombre,
    c.servicio,
    c.estado_cama
