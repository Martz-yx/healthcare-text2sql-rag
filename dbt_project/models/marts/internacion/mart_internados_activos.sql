{{ config(materialized='view') }}

-- mart_internados_activos: Pacientes actualmente internados.
-- CODIFICA la regla de negocio: fin_del_evento='0' AND is_outdated=false.
-- La AI solo necesita: SELECT * FROM dbt_analytics.mart_internados_activos
--
-- Incluye: paciente, médico, ubicación completa (edificio>piso>sala>cama),
-- servicio, hospital, diagnóstico de ingreso, y días internado.

SELECT
    ha.codigo_establecimiento,
    ha.codigo_asignacion,
    ha.codigo_paciente,
    p.nombre_completo AS nombre_paciente,
    p.sexo AS sexo_paciente,
    ha.edad_formateada AS edad_ingreso,
    ha.codigo_medico,
    u.nombre_completo AS medico_tratante,
    est.nombre AS hospital,
    serv.nombre AS servicio,
    ed.nombre_edificio AS edificio,
    pi.nombre_piso AS piso,
    sal.nombre_sala AS sala,
    ha.nombre_cama AS cama,
    ha.tipo_cama_desc AS tipo_cama,
    ha.hospitalario_fecha AS fecha_ingreso,
    ha.hospitalario_hora AS hora_ingreso,
    CURRENT_DATE - ha.hospitalario_fecha AS dias_internado,
    ha.nivel_urgencia,
    ha.re_hospitalizar_en_14_dias AS es_rehospitalizacion,
    ha.seguro_medico

FROM {{ ref('stg_hospitalario_asignacion') }} ha

-- Datos del paciente
JOIN {{ ref('stg_paciente') }} p
    ON ha.codigo_paciente = p.codigo_paciente

-- Médico tratante
LEFT JOIN {{ ref('stg_usuario') }} u
    ON ha.codigo_medico = u.codigo_usuario

-- Hospital
LEFT JOIN {{ ref('stg_establecimiento') }} est
    ON ha.codigo_establecimiento = est.codigo_establecimiento

-- Servicio
LEFT JOIN {{ ref('stg_servicio') }} serv
    ON ha.codigo_servicio = serv.codigo_servicio

-- Ubicación física
LEFT JOIN {{ ref('stg_edificio') }} ed
    ON ha.codigo_establecimiento = ed.codigo_establecimiento
    AND ha.codigo_edificio = ed.codigo_edificio
LEFT JOIN {{ ref('stg_piso') }} pi
    ON ha.codigo_establecimiento = pi.codigo_establecimiento
    AND ha.codigo_piso = pi.codigo_piso
LEFT JOIN {{ ref('stg_sala') }} sal
    ON ha.codigo_establecimiento = sal.codigo_establecimiento
    AND ha.codigo_sala = sal.codigo_sala

-- ═══════════════════════════════════════════════════════════
-- REGLA DE NEGOCIO CRÍTICA: Solo internados activos
-- fin_del_evento = '0' → no ha egresado
-- is_outdated = false  → no fue reemplazado por transferencia
-- ═══════════════════════════════════════════════════════════
WHERE ha.fin_del_evento = '0'
  AND ha.is_outdated = false
