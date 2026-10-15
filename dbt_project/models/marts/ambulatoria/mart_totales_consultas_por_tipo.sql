{{ config(materialized='view') }}

-- mart_totales_consultas_por_tipo: Agrupa la cantidad de consultas y pacientes por fecha, establecimiento, región y tipo.
-- Utiliza Arquitectura Lambda: une histórico precalculado con el día de hoy en tiempo real.

SELECT
    fecha_consulta,
    hospital,
    region,
    tipo_consulta,
    total_consultas,
    total_pacientes_distintos,
    total_admisionistas,
    total_medicos,
    total_enfermeros,
    total_farmaceuticos
FROM {{ ref('int_totales_consultas_historico') }}

UNION ALL

SELECT
    fecha_consulta,
    hospital,
    region,
    tipo_consulta,
    total_consultas,
    total_pacientes_distintos,
    total_admisionistas,
    total_medicos,
    total_enfermeros,
    total_farmaceuticos
FROM {{ ref('int_totales_consultas_hoy') }}
