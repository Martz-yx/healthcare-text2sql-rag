SELECT
    pa.*,
    CASE pa.tipo_consulta
        WHEN 'A' THEN 'Ambulatoria'
        WHEN 'U' THEN 'Urgencia'
        WHEN 'T' THEN 'Teleconsulta'
        WHEN 'I' THEN 'Internación'
        WHEN 'E' THEN 'Extramural'
        WHEN 'D' THEN 'Domiciliaria'
        ELSE pa.tipo_consulta
    END AS tipo_consulta_desc,
    {{ edad_con_unidad('pa') }} AS edad_formateada
FROM {{ source('his', 'paciente_asignacion') }} pa
