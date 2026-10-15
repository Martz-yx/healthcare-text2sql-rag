-- stg_usuario: Vista limpia de usuarios del sistema (médicos, enfermeros, admin).

SELECT
    u.codigo_usuario,
    {{ nombre_medico('u') }} AS nombre_completo,
    u.nombres,
    u.apellidos,
    u.pin_usuario AS nickname,
    CASE 
        WHEN u.estado = '1' THEN 'ACTIVO'
        ELSE 'INACTIVO'
    END AS estado,
    u.creacion_fecha AS fecha_registro

FROM {{ source('his', 'usuario') }} u
ORDER BY u.codigo_usuario, u.creacion_fecha DESC
