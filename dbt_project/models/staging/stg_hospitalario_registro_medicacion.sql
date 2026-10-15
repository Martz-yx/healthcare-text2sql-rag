SELECT *
FROM {{ source('his', 'hospitalario_registro_medicacion') }}
