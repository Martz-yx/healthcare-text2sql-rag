SELECT
    *,
    CASE orden WHEN 1 THEN 'Principal' ELSE 'Secundario' END AS tipo_diagnostico_desc,
    CASE nuevo WHEN '1' THEN 'Nuevo' WHEN '0' THEN 'Preexistente' ELSE 'No especificado' END AS diagnostico_nuevo_desc
FROM {{ source('his', 'consulta_diagnostico') }}