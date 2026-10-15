{{ config(materialized='view') }}

-- mart_diagnosticos_ambulatorios: Diagnósticos CIE-10 de consultas ambulatorias.
-- Pre-une la jerarquía CIE-10 completa (capítulo > grupo > subgrupo > diagnóstico)
-- y la geografía completa tanto del hospital (region, distrito_hospital) como del paciente (region_residencia, departamento_residencia, distrito_residencia, barrio_residencia).

SELECT
    cd.codigo_establecimiento,
    cd.codigo_asignacion,
    pa.codigo_paciente,
    p.nombre_completo AS nombre_paciente,
    pa.consulta_fecha AS fecha_consulta,
    est.nombre AS hospital,
    r.nombre_region AS region,
    dis_est.nombre_distrito AS distrito_hospital,
    serv.nombre AS servicio,

    -- Residencia del paciente
    reg_res.nombre_region AS region_residencia,
    dep.nombre_departamento AS departamento_residencia,
    dis.nombre_distrito AS distrito_residencia,
    bar.nombre_barrio AS barrio_residencia,
    -- Diagnóstico
    cd.orden,
    cd.tipo_diagnostico_desc AS tipo_diagnostico,
    cd.codigo_cie10a || cd.codigo_cie10b AS codigo_cie10,
    cd.nombre_cie10 AS diagnostico,
    cd.diagnostico_nuevo_desc AS diagnostico_nuevo,

    -- Jerarquía CIE-10
    sg.nombre_subgrupo AS subgrupo_cie10,
    g.nomgru AS grupo_cie10,
    cap.nomcap AS capitulo_cie10

FROM {{ ref('stg_consulta_diagnostico') }} cd

JOIN {{ ref('stg_paciente_asignacion') }} pa
    ON cd.codigo_establecimiento = pa.codigo_establecimiento
    AND cd.codigo_asignacion = pa.codigo_asignacion

JOIN {{ ref('stg_paciente') }} p
    ON pa.codigo_paciente = p.codigo_paciente

LEFT JOIN {{ ref('stg_establecimiento') }} est
    ON cd.codigo_establecimiento = est.codigo_establecimiento

LEFT JOIN {{ ref('stg_region') }} r
    ON est.codigo_region = r.codigo_region

LEFT JOIN {{ ref('stg_distrito') }} dis_est
    ON est.codigo_region = dis_est.codigo_departamento
    AND est.codigo_distrito = dis_est.codigo_distrito

LEFT JOIN {{ ref('stg_servicio') }} serv
    ON pa.codigo_servicio = serv.codigo_servicio

-- Residencia del paciente
LEFT JOIN {{ ref('stg_departamento') }} dep
    ON p.cod_departamento_residencia = dep.codigo_departamento

LEFT JOIN {{ ref('stg_distrito') }} dis
    ON p.cod_departamento_residencia = dis.codigo_departamento
    AND p.cod_distrito_residencia = dis.codigo_distrito

LEFT JOIN {{ ref('stg_region') }} reg_res
    ON dis.codigo_region = reg_res.codigo_region
    AND dis.codigo_subregion = reg_res.codigo_subregion

LEFT JOIN {{ ref('stg_barrio') }} bar
    ON p.cod_departamento_residencia = bar.codigo_departamento
    AND p.cod_distrito_residencia = bar.codigo_distrito
    AND p.cod_barrio_residencia = bar.codigo_barrio

-- Jerarquía CIE-10
LEFT JOIN {{ ref('stg_subgrupo_cie10') }} sg
    ON cd.codigo_cie10a = sg.codigo_cie10a
LEFT JOIN {{ ref('stg_grupo_cie10') }} g
    ON sg.codgru = g.codgru
LEFT JOIN {{ ref('stg_cap_cie10') }} cap
    ON g.codcap = cap.codcap
