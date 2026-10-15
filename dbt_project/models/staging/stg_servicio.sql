-- stg_servicio: Vista limpia de servicios/departamentos médicos.

SELECT
    s.codigo_servicio,
    s.nombre_servicio AS nombre,
    s.codigo_clase,
    CASE s.activo
        WHEN '1' THEN true
        ELSE false
    END AS activo

FROM {{ source('his', 'servicio') }} s
