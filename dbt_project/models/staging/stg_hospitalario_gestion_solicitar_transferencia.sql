SELECT *
FROM {{ source('his', 'hospitalario_gestion_solicitar_transferencia') }}
