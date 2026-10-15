-- stg_paciente: Vista limpia de pacientes con columnas decodificadas.
-- Centraliza la lógica de sexo, estado civil y nombre completo.

SELECT
    p.codigo_paciente,
    p.tipo_documento,
    p.codigo_ficha,
    {{ nombre_paciente('p') }} AS nombre_completo,
    p.primer_nombre,
    p.segundo_nombre,
    p.primer_apellido,
    p.segundo_apellido,
    p.fecha_nacimiento,
    {{ decodificar_sexo('p') }} AS sexo,
    CASE p.estado_civil
        WHEN '2' THEN 'Soltero/a'
        WHEN '3' THEN 'Casado/a'
        WHEN '4' THEN 'Divorciado/a'
        WHEN '5' THEN 'Viudo/a'
        WHEN '6' THEN 'Unión libre'
        ELSE 'No especificado'
    END AS estado_civil,
    p.cod_departamento_residencia,
    p.cod_distrito_residencia,
    p.cod_barrio_residencia,
    CASE p.area
        WHEN '0' THEN 'Urbano'
        WHEN '1' THEN 'Rural'
        ELSE 'No especificado'
    END AS area_residencia,
    p.codigo_nacionalidad,
    p.seguro_medico,
    p.creacion_fecha AS fecha_registro,
    p.is_desconocido

FROM {{ source('his', 'paciente') }} p
