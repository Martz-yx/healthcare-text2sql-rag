{{ config(materialized='view') }}

-- mart_signos_vitales: Signos vitales registrados en preconsulta (triaje).
-- Útil para preguntas como "¿cuál fue la presión del paciente?"

SELECT
    pre.codigo_establecimiento,
    pre.codigo_asignacion,
    pa.codigo_paciente,
    p.nombre_completo AS nombre_paciente,
    pa.consulta_fecha AS fecha_consulta,
    pre.creacion_fecha AS fecha_triaje,
    pre.creacion_hora AS hora_triaje,
    est.nombre AS hospital,
    serv.nombre AS servicio,

    -- Signos vitales
    pre.peso AS peso_kg,
    pre.talla AS talla_cm,
    pre.indice_masa_corporal AS imc,
    pre.toaxilar_rectal AS temperatura_c,
    pre.presion_arterial_sis AS presion_sistolica,
    pre.presion_arterial_dias AS presion_diastolica,
    NULLIF(TRIM(pre.pulso), '')::numeric::integer AS pulso_por_min,
    NULLIF(TRIM(pre.frecuencia_respiratoria), '')::numeric::integer AS frecuencia_respiratoria,
    NULLIF(TRIM(pre.frecuencia_cardiaca), '')::numeric::integer AS frecuencia_cardiaca,
    pre.saturacion_oxigeno AS spo2_porcentaje,
    pre.circunferencia_abdominal AS circunf_abdominal_cm,

    -- Estado nutricional
    pre.estado_nutricional_desc AS estado_nutricional,

    -- Embarazo
    pre.embarazada_bool AS embarazada,
    pre.fum AS fecha_ultima_menstruacion,

    -- Pediatría
    pre.perimetro_craneal AS perimetro_craneal_cm,
    pre.hba1c AS hemoglobina_glicosilada

FROM {{ ref('stg_preconsulta') }} pre

JOIN {{ ref('stg_paciente_asignacion') }} pa
    ON pre.codigo_establecimiento = pa.codigo_establecimiento
    AND pre.codigo_asignacion = pa.codigo_asignacion

JOIN {{ ref('stg_paciente') }} p
    ON pa.codigo_paciente = p.codigo_paciente

LEFT JOIN {{ ref('stg_establecimiento') }} est
    ON pre.codigo_establecimiento = est.codigo_establecimiento

LEFT JOIN {{ ref('stg_servicio') }} serv
    ON pa.codigo_servicio = serv.codigo_servicio



