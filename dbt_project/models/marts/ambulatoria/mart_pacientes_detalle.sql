{{ config(materialized='view') }}

-- mart_pacientes_detalle: Datos demográficos detallados del paciente.
-- Cruza la tabla principal de pacientes con catálogos auxiliares como país, barrio, distrito y región.
-- Ideal para que la IA consulte demografía y atributos estáticos.

SELECT
    p.codigo_paciente,
    p.tipo_documento,
    p.codigo_ficha,
    p.nombre_completo,
    p.primer_nombre,
    p.primer_apellido,
    p.fecha_nacimiento,
    EXTRACT(YEAR FROM age(CURRENT_DATE, p.fecha_nacimiento)) AS edad_actual,
    p.sexo,
    p.estado_civil,
    p.cod_barrio_residencia,
    b.nombre_barrio,
    p.cod_distrito_residencia,
    d.nombre_distrito,
    p.cod_departamento_residencia,
    d.codigo_region,
    r.nombre_region,
    r.nombre_region AS departamento_region,
    pais.nombre_nacionalidad AS nacionalidad,
    p.area_residencia,
    p.seguro_medico,
    p.fecha_registro,
    p.is_desconocido
FROM {{ ref('stg_paciente') }} p
LEFT JOIN {{ ref('stg_barrio') }} b 
    ON p.cod_departamento_residencia = b.codigo_departamento 
    AND p.cod_distrito_residencia = b.codigo_distrito 
    AND p.cod_barrio_residencia = b.codigo_barrio
LEFT JOIN {{ ref('stg_distrito') }} d 
    ON p.cod_departamento_residencia = d.codigo_departamento 
    AND p.cod_distrito_residencia = d.codigo_distrito
LEFT JOIN {{ ref('stg_region') }} r 
    ON d.codigo_region = r.codigo_region 
    AND d.codigo_subregion = r.codigo_subregion
LEFT JOIN {{ ref('stg_pais') }} pais 
    ON p.codigo_nacionalidad = pais.codigo_nacimiento

