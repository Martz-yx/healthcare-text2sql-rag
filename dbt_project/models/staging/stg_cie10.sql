-- stg_cie10: Vista limpia de diagnósticos CIE-10 con jerarquía completa.
-- Une los 4 niveles: capítulo > grupo > subgrupo > diagnóstico detallado.

SELECT
    c.codigo_cie10a,
    c.codigo_cie10b,
    c.codigo_cie10a || c.codigo_cie10b AS codigo_cie10_completo,
    c.nombre_cie10 AS diagnostico,
    sg.nombre_subgrupo AS subgrupo,
    g.nomgru AS grupo,
    g.codgru AS codigo_grupo,
    cap.nomcap AS capitulo,
    cap.codcap AS codigo_capitulo

FROM {{ source('his', 'cie10') }} c
LEFT JOIN {{ source('his', 'subgrupo_cie10') }} sg
    ON c.codigo_cie10a = sg.codigo_cie10a
LEFT JOIN {{ source('his', 'grupo_cie10') }} g
    ON sg.codgru = g.codgru
LEFT JOIN {{ source('his', 'cap_cie10') }} cap
    ON g.codcap = cap.codcap
