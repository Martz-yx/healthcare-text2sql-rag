SELECT *
FROM {{ source('his', 'long_term_prescription_details') }}
