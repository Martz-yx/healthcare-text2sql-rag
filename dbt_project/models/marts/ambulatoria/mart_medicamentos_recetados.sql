{{ config(materialized='view') }}

-- mart_medicamentos_recetados: Medicamentos recetados en consultas ambulatorias.
-- Pre-une el catálogo de medicamentos y la vía de administración.
-- Excluye recetas eliminadas (isdc = 'Y').

SELECT
    cm.codigo_establecimiento,
    cm.codigo_asignacion,
    pa.codigo_paciente,
    {{ nombre_paciente('p') }} AS nombre_paciente,
    pa.consulta_fecha AS fecha_consulta,
    est.nombre AS hospital,
    serv.nombre AS servicio,
    pa.codigo_medico,
    {{ nombre_medico('u') }} AS medico_prescriptor,

    -- Medicamento
    med.nombre_droga AS medicamento,
    med.presentacion,
    med.forma_farmaceutica,
    med.concentracion,
    cm.dosis,
    cm.forma_uso AS instrucciones,
    cm.dias_uso AS dias_tratamiento,
    cm.numero_total AS cantidad_recetada,
    cm.cantidad_dispensada,
    CASE cm.estado
        WHEN 'Completo' THEN 'Completo'
        WHEN 'En Proceso' THEN 'En proceso'
        WHEN 'Eliminado' THEN 'Eliminado'
        ELSE COALESCE(cm.estado, 'No especificado')
    END AS estado_receta

FROM {{ ref('stg_consulta_medicamento') }} cm

JOIN {{ ref('stg_paciente_asignacion') }} pa
    ON cm.codigo_establecimiento = pa.codigo_establecimiento
    AND cm.codigo_asignacion = pa.codigo_asignacion

JOIN {{ ref('stg_paciente') }} p
    ON pa.codigo_paciente = p.codigo_paciente

LEFT JOIN {{ ref('stg_medicamento_total') }} med
    ON cm.codigo_medicamento = med.codigo_medicamento

LEFT JOIN {{ ref('stg_usuario') }} u
    ON pa.codigo_medico = u.codigo_usuario

LEFT JOIN {{ ref('stg_establecimiento') }} est
    ON cm.codigo_establecimiento = est.codigo_establecimiento

LEFT JOIN {{ ref('stg_servicio') }} serv
    ON pa.codigo_servicio = serv.codigo_servicio

WHERE COALESCE(cm.isdc, 'N') != 'Y'  -- Excluir eliminados

