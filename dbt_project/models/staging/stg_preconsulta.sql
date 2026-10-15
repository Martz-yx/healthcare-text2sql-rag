SELECT
    *,
    CASE estado_nutricional::text
        WHEN '0' THEN 'Normal'
        WHEN '1' THEN 'Riesgo desnutrición'
        WHEN '2' THEN 'Desnutrición moderada'
        WHEN '3' THEN 'Desnutrición grave'
        WHEN '4' THEN 'Sobrepeso'
        WHEN '5' THEN 'Obesidad'
        ELSE 'No evaluado'
    END AS estado_nutricional_desc,
    CASE embarazada::text WHEN '1' THEN true ELSE false END AS embarazada_bool
FROM {{ source('his', 'preconsulta') }}