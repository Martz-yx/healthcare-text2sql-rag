{{ config(materialized='view') }}

-- mart_ubicacion_camas: Ubicación detallada de las camas.
-- Incluye piso, sala, edificio, y estado de la cama.
-- Útil SOLO para preguntas que requieran ubicaciones exactas (ej. "Camas en piso 3").

SELECT
    c.codigo_establecimiento,
    est.nombre AS hospital,
    c.edificio,
    c.piso,
    c.sala,
    c.servicio,
    c.nombre_cama AS cama,
    c.tipo_cama,
    c.estado_cama AS estado,
    c.asignacion_actual
FROM {{ ref('stg_cama') }} c
LEFT JOIN {{ ref('stg_establecimiento') }} est
    ON c.codigo_establecimiento = est.codigo_establecimiento
WHERE c.cama_activa = true
