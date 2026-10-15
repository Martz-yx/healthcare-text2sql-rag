-- stg_cama: Vista limpia de camas con su ubicación completa y estado actual.
-- Pre-une: cama + sala + piso + edificio + cama_estado.
-- Elimina la necesidad de 4 JOINs cada vez que la AI pregunta sobre camas.

SELECT
    c.codigo_establecimiento,
    c.codigo_cama,
    c.nombre_cama,
    CASE c.tipo_cama
        WHEN 'G' THEN 'General'
        WHEN 'T' THEN 'UTI/Terapia Intensiva'
        ELSE c.tipo_cama
    END AS tipo_cama,
    s.nombre_sala AS sala,
    s.codigo_sala,
    p.nombre_piso AS piso,
    p.codigo_piso,
    ed.nombre_edificio AS edificio,
    ed.codigo_edificio,
    serv.nombre_servicio AS servicio,
    CASE ce.estado
        WHEN '1' THEN 'Disponible'
        WHEN '2' THEN 'Ocupado'
        WHEN '3' THEN 'Preparación'
        WHEN '4' THEN 'Aislado'
        WHEN '5' THEN 'En reparación'
        ELSE 'Desconocido'
    END AS estado_cama,
    ce.codigo_asignacion AS asignacion_actual,
    CASE c.activo
        WHEN 'Y' THEN true
        ELSE false
    END AS cama_activa

FROM {{ source('his', 'cama') }} c
LEFT JOIN {{ source('his', 'sala') }} s
    ON c.codigo_establecimiento = s.codigo_establecimiento
    AND c.codigo_sala = s.codigo_sala
LEFT JOIN {{ source('his', 'piso') }} p
    ON c.codigo_establecimiento = p.codigo_establecimiento
    AND c.codigo_piso = p.codigo_piso
LEFT JOIN {{ source('his', 'edificio') }} ed
    ON c.codigo_establecimiento = ed.codigo_establecimiento
    AND c.codigo_edificio = ed.codigo_edificio
LEFT JOIN {{ source('his', 'servicio') }} serv
    ON c.codigo_servicio = serv.codigo_servicio
LEFT JOIN {{ source('his', 'cama_estado') }} ce
    ON c.codigo_establecimiento = ce.codigo_establecimiento
    AND c.codigo_cama = ce.codigo_cama
