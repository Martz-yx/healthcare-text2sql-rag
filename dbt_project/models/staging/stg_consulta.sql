SELECT
    *,
    CASE derivar
        WHEN '0' THEN 'No aplica'
        WHEN '1' THEN 'Se refiere'
        WHEN '2' THEN 'Internación'
        WHEN '3' THEN 'Domicilio'
        WHEN '4' THEN 'Fuga/No se realizó'
        WHEN '5' THEN 'Muerte'
        WHEN '6' THEN 'Re-Evaluar'
        WHEN '7' THEN 'Reasignar'
        ELSE 'No registrado'
    END AS derivar_desc
FROM {{ source('his', 'consulta') }}
