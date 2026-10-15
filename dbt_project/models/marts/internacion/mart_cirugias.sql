-- mart_cirugias: Procedimientos quirúrgicos realizados durante internaciones.
-- Incluye paciente, cirujano, diagnósticos, y duración.

SELECT
    cp.codigo_establecimiento,
    cp.codigo_asignacion,
    ha.codigo_paciente,
    p.nombre_completo AS nombre_paciente,
    p.sexo AS sexo_paciente,
    est.nombre AS hospital,
    serv.nombre AS servicio,

    -- Datos de la cirugía
    cp.tiempo_ejecucion AS fecha_hora_cirugia,
    cp.cirugia_realizada,
    cp.diagnostico_preoperatorio,
    cp.diagnostico_posoperatorio,
    cp.descripcion AS descripcion_procedimiento,
    cp.complicaciones,
    cp.tiempo_total_cirugia AS duracion_minutos,
    cp.tipo_anestesia,
    cp.tiempo_anestesia AS duracion_anestesia_minutos,
    cp.perdida_estimada_sangre AS sangre_perdida_ml,
    cp.muestra AS muestras_patologia,
    cp.cirujano AS cirujano_json,
    cp.ayudante AS ayudante_json,
    cp.anestesista AS anestesista_json,

    cp.estado_desc AS estado

FROM {{ ref('stg_hospitalario_cirugia_procedimiento') }} cp

JOIN {{ ref('stg_hospitalario_asignacion') }} ha
    ON cp.codigo_establecimiento = ha.codigo_establecimiento
    AND cp.codigo_asignacion = ha.codigo_asignacion
    AND ha.orden_asignacion = 1

JOIN {{ ref('stg_paciente') }} p
    ON ha.codigo_paciente = p.codigo_paciente

LEFT JOIN {{ ref('stg_establecimiento') }} est
    ON cp.codigo_establecimiento = est.codigo_establecimiento

LEFT JOIN {{ ref('stg_servicio') }} serv
    ON ha.codigo_servicio = serv.codigo_servicio

WHERE cp.estado != 'D'  -- Excluir eliminados
