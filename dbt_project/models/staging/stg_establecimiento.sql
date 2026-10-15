-- stg_establecimiento: Vista limpia de establecimientos de salud.

SELECT
    e.codigo_establecimiento,
    e.nombre_establecimiento AS nombre,
    e.codigo_region,
    e.codigo_distrito,
    e.direccion,
    e.telefono,
    e.email,
    CASE e.area
        WHEN '0' THEN 'Urbano'
        WHEN '1' THEN 'Rural'
        ELSE 'No especificado'
    END AS area,
    e.estado,
    e.latitud,
    e.longitud

FROM {{ source('his', 'establecimiento') }} e
