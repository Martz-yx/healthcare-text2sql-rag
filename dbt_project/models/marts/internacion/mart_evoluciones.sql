-- mart_evoluciones: Notas de evolución médica (SOAP) durante internaciones.
-- Cada fila es una nota de evolución con sus 4 componentes SOAP.

SELECT
    ev.codigo_establecimiento,
    ev.codigo_asignacion,
    ev.codigo_evolucion,
    ha.codigo_paciente,
    p.nombre_completo AS nombre_paciente,
    est.nombre AS hospital,
    serv_ev.nombre AS servicio_evolucion,

    -- SOAP
    ev.tiempo_ejecucion AS fecha_hora_evolucion,
    ev.subjetivo,
    ev.objetivo,
    ev.analisis,
    ev.plan,

    -- Médico que escribió
    u.nombre_completo AS medico_evolucion,

    ev.tipo_evolucion_desc AS tipo_evolucion,
    ev.estado_desc AS estado

FROM {{ ref('stg_hospitalario_evolucion') }} ev

JOIN {{ ref('stg_hospitalario_asignacion') }} ha
    ON ev.codigo_establecimiento = ha.codigo_establecimiento
    AND ev.codigo_asignacion = ha.codigo_asignacion
    AND ha.orden_asignacion = 1

JOIN {{ ref('stg_paciente') }} p
    ON ha.codigo_paciente = p.codigo_paciente

LEFT JOIN {{ ref('stg_usuario') }} u
    ON ev.creacion_usuario = u.codigo_usuario

LEFT JOIN {{ ref('stg_establecimiento') }} est
    ON ev.codigo_establecimiento = est.codigo_establecimiento

LEFT JOIN {{ ref('stg_servicio') }} serv_ev
    ON ev.codigo_servicio = serv_ev.codigo_servicio

WHERE ev.estado != 'D'  -- Excluir eliminados
