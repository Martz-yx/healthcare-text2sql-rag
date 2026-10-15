{{ config(
    materialized='incremental',
    unique_key=['fecha_consulta', 'codigo_establecimiento', 'tipo_consulta_raw']
) }}

SELECT
    pa.consulta_fecha AS fecha_consulta,
    e.codigo_establecimiento,
    e.nombre AS hospital,
    r.nombre_region AS region,
    pa.tipo_consulta AS tipo_consulta_raw,
    CASE pa.tipo_consulta
        WHEN 'A' THEN 'Ambulatoria'
        WHEN 'U' THEN 'Urgencia'
        WHEN 'T' THEN 'Teleconsulta'
        WHEN 'I' THEN 'Internación'
        WHEN 'E' THEN 'Extramural'
        WHEN 'D' THEN 'Domiciliaria'
        ELSE pa.tipo_consulta
    END AS tipo_consulta,
    COUNT(DISTINCT pa.codigo_establecimiento || '-' || pa.codigo_asignacion) AS total_consultas,
    COUNT(DISTINCT pa.codigo_paciente) AS total_pacientes_distintos,
    COUNT(DISTINCT pa.creacion_usuario) AS total_admisionistas,
    COUNT(DISTINCT c.creacion_usuario) AS total_medicos,
    COUNT(DISTINCT pr.creacion_usuario) AS total_enfermeros,
    COUNT(DISTINCT cm.creacion_usuario) AS total_farmaceuticos
FROM {{ ref('stg_paciente_asignacion') }} pa
JOIN {{ ref('stg_establecimiento') }} e
    ON pa.codigo_establecimiento = e.codigo_establecimiento
JOIN {{ ref('stg_region') }} r
    ON e.codigo_region = r.codigo_region
LEFT JOIN {{ ref('stg_consulta') }} c
    ON pa.codigo_establecimiento = c.codigo_establecimiento AND pa.codigo_asignacion = c.codigo_asignacion
LEFT JOIN {{ ref('stg_preconsulta') }} pr
    ON pa.codigo_establecimiento = pr.codigo_establecimiento AND pa.codigo_asignacion = pr.codigo_asignacion
LEFT JOIN {{ ref('stg_consulta_medicamento') }} cm
    ON pa.codigo_establecimiento = cm.codigo_establecimiento AND pa.codigo_asignacion = cm.codigo_asignacion
WHERE pa.consulta_fecha < CURRENT_DATE
{% if is_incremental() %}
  AND pa.consulta_fecha >= (SELECT COALESCE(MAX(fecha_consulta), '2000-01-01') FROM {{ this }})
{% endif %}
GROUP BY
    pa.consulta_fecha,
    e.codigo_establecimiento,
    e.nombre,
    r.nombre_region,
    pa.tipo_consulta
