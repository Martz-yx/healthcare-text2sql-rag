{{ config(materialized='view') }}

SELECT
    cd.creacion_fecha AS fecha_diagnostico,
    e.nombre AS hospital,
    r.nombre_region AS region,
    cd.nombre_cie10 AS diagnostico,
    COUNT(*) AS total_casos
FROM {{ ref('stg_consulta_diagnostico') }} cd
JOIN {{ ref('stg_establecimiento') }} e
    ON cd.codigo_establecimiento = e.codigo_establecimiento
JOIN {{ ref('stg_region') }} r
    ON e.codigo_region = r.codigo_region
WHERE cd.creacion_fecha >= CURRENT_DATE
GROUP BY
    cd.creacion_fecha,
    e.nombre,
    r.nombre_region,
    cd.nombre_cie10
