{{ config(materialized='view') }}

-- mart_diagnosticos_top_diarios: Cuenta la cantidad de veces que se registra cada diagnóstico CIE-10 por fecha y establecimiento.
-- Utiliza Arquitectura Lambda: une histórico precalculado con el día de hoy en tiempo real.

SELECT
    fecha_diagnostico,
    hospital,
    region,
    diagnostico,
    total_casos
FROM {{ ref('int_diagnosticos_top_historico') }}

UNION ALL

SELECT
    fecha_diagnostico,
    hospital,
    region,
    diagnostico,
    total_casos
FROM {{ ref('int_diagnosticos_top_hoy') }}
