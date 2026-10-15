SELECT
    ha.*,
    CASE ha.tipo_cama
        WHEN 'G' THEN 'General'
        WHEN 'T' THEN 'UTI/Terapia Intensiva'
        ELSE ha.tipo_cama
    END AS tipo_cama_desc,
    {{ edad_con_unidad('ha') }} AS edad_formateada
FROM {{ source('his', 'hospitalario_asignacion') }} ha