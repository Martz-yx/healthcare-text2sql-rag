{{ config(materialized='view') }}

-- mart_paciente_historia_clinica: Timeline unificado de todas las interacciones del paciente.
-- Une atenciones ambulatorias, urgencias e internaciones en un solo flujo ordenado por fecha.

WITH ambulatoria AS (
    SELECT
        pa.codigo_paciente,
        pa.consulta_fecha AS fecha_atencion,
        'Ambulatoria / Urgencias' AS tipo_atencion,
        e.nombre AS hospital,
        s.nombre AS servicio,
        c.motivo_consulta AS detalle,
        pa.codigo_establecimiento
    FROM {{ ref('stg_paciente_asignacion') }} pa
    LEFT JOIN {{ ref('stg_consulta') }} c 
        ON pa.codigo_establecimiento = c.codigo_establecimiento 
        AND pa.codigo_asignacion = c.codigo_asignacion
    LEFT JOIN {{ ref('stg_establecimiento') }} e 
        ON pa.codigo_establecimiento = e.codigo_establecimiento
    LEFT JOIN {{ ref('stg_servicio') }} s 
        ON pa.codigo_servicio = s.codigo_servicio
),

internacion AS (
    SELECT
        ha.codigo_paciente,
        ha.hospitalario_fecha AS fecha_atencion,
        'Internación' AS tipo_atencion,
        e.nombre AS hospital,
        s.nombre AS servicio,
        CONCAT('Cama: ', ha.codigo_cama) AS detalle,
        ha.codigo_establecimiento
    FROM {{ ref('stg_hospitalario_asignacion') }} ha
    LEFT JOIN {{ ref('stg_establecimiento') }} e 
        ON ha.codigo_establecimiento = e.codigo_establecimiento
    LEFT JOIN {{ ref('stg_servicio') }} s 
        ON ha.codigo_servicio = s.codigo_servicio
)

SELECT * FROM ambulatoria
UNION ALL
SELECT * FROM internacion
ORDER BY codigo_paciente, fecha_atencion DESC
