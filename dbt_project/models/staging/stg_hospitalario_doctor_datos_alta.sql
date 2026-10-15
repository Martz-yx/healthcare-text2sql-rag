SELECT
    *,
    CASE condicion_egreso
        WHEN '1' THEN 'Curado/a'
        WHEN '2' THEN 'Mejorado/a'
        WHEN '3' THEN 'Estacionario/a'
        WHEN '4' THEN 'Empeorado/a'
        WHEN '5' THEN 'Fallecido/a'
        ELSE 'No especificado'
    END AS condicion_egreso_desc,
    CASE tipo_egreso
        WHEN '1' THEN 'Alta médica'
        WHEN '2' THEN 'Traslado'
        WHEN '3' THEN 'Retiro voluntario'
        WHEN '4' THEN 'Fuga'
        WHEN '5' THEN 'Defunción'
        WHEN '10' THEN 'Rechazo'
        ELSE 'No especificado'
    END AS tipo_egreso_desc
FROM {{ source('his', 'hospitalario_doctor_datos_alta') }}