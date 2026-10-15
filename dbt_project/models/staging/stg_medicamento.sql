-- stg_medicamento: Vista limpia del catálogo de medicamentos.

SELECT
    mt.codigo_medicamento,
    mt.nombre_droga AS nombre,
    mt.presentacion,
    mt.forma_farmaceutica,
    mt.concentracion

FROM {{ source('his', 'medicamento_total') }} mt
