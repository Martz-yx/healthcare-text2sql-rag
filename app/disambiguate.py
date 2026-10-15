"""
Hospital Disambiguation Module

When a user mentions an ambiguous hospital/location name (e.g. "San Juan"),
this module queries the `establecimiento` table to find all matching facilities
and presents interactive buttons for the user to select the correct one.
"""

import re
import logging
from typing import Optional

import psycopg2
import chainlit as cl
import asyncio

logger = logging.getLogger(__name__)

# Common words that should NOT be treated as hospital/location keywords.
# These are typical Spanish medical/query terms that would cause false positives.
_STOP_WORDS = {
    # Common query words
    "cuantos", "cuantas", "cuanto", "cuanta", "cuales", "donde", "cuando",
    "como", "porque", "quien", "quienes", "cuál", "cuáles", "dónde", "cuándo",
    "cómo", "quién", "quiénes", "cuántos", "cuántas",
    # Medical terms
    "paciente", "pacientes", "doctor", "doctores", "medico", "medicos",
    "médico", "médicos", "enfermero", "enfermera", "consulta", "consultas",
    "diagnostico", "diagnóstico", "diagnosticos", "diagnósticos",
    "internado", "internados", "internacion", "internación", "internaciones",
    "cama", "camas", "sala", "salas", "piso", "pisos",
    "medicamento", "medicamentos", "cirugia", "cirugía", "cirugias",
    "urgencia", "urgencias", "emergencia", "emergencias",
    "alta", "altas", "egreso", "egresos", "ingreso", "ingresos",
    "hoy", "ayer", "semana", "mes", "año", "total", "promedio",
    # Common verbs/prepositions/query terms
    "hay", "hubo", "tiene", "tienen", "fue", "fueron", "esta", "están",
    "por", "para", "con", "sin", "desde", "hasta", "entre", "sobre",
    "todos", "todas", "cada", "mas", "más", "menos", "mejor", "peor",
    "list", "listar", "mostrar", "obtener", "buscar", "ver", "dame",
    "caso", "casos", "dengue",
    # Months (Spanish & English)
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "setiembre", "octubre", "noviembre", "diciembre",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    # Geographic & administrative division terms (Spanish & English)
    "region", "región", "regiones", "departamento", "departamentos",
    "distrito", "distritos", "barrio", "barrios", "ciudad", "ciudades",
    "localidad", "localidades", "municipio", "municipios", "zona", "zonas",
    "pais", "país", "paises", "países", "estado", "estados", "provincia", "provincias",
    "capital",
    "department", "departments", "district", "districts", "city", "cities",
    "country", "countries", "area", "areas", "zone", "zones", "state", "states",
    "province", "provinces",
    # English equivalents
    "how", "many", "much", "what", "which", "where", "when", "who",
    "patients", "doctors", "today", "yesterday", "week", "month", "year",
    "total", "hospital", "hospitals", "the", "and", "for", "from",
    # dbt/technical
    "mart", "dbt", "analytics", "tabla", "tablas",
    # Countries and scope words
    "nacional",
}

# Known hospital prefixes in the hospital system
_HOSPITAL_PREFIXES = {"HR", "PS", "USF", "CS", "HN", "HD", "HG", "HM"}

_GEOGRAPHIC_INDICATORS = {
    "region", "región", "regiones", "departamento", "departamentos",
    "distrito", "distritos", "barrio", "barrios", "zona", "zonas",
    "department", "departments", "district", "districts", "city", "cities",
}


def _is_region_or_department_context(candidate: str, text: str) -> bool:
    """
    Check if candidate keyword is used in a geographic region/department context
    (e.g., "Capital region", "región Capital", "departamento Central", "Central department").
    """
    cand_lower = candidate.lower().strip()
    if cand_lower in _STOP_WORDS:
        return True

    text_lower = text.lower()
    # Check if candidate is preceded or followed by a geographic indicator
    indicators_pattern = "|".join(re.escape(g) for g in _GEOGRAPHIC_INDICATORS)
    pattern1 = r'\b(' + indicators_pattern + r')\s+(?:de\s+|del\s+|d\'\s+)?\b' + re.escape(cand_lower) + r'\b'
    pattern2 = r'\b' + re.escape(cand_lower) + r'\s+(' + indicators_pattern + r')\b'
    
    if re.search(pattern1, text_lower) or re.search(pattern2, text_lower):
        return True
    return False


def _extract_location_keywords(text: str) -> list[str]:
    """
    Extract potential location/hospital keywords from the user's text.
    
    Strategy:
    1. Look for known hospital prefix patterns (e.g. "HR REGIONAL")
    2. Look for words after location prepositions ("en", "de", "del")
    3. Look for capitalized words that aren't common terms or region names
    """
    keywords = []
    
    # Strategy 1: Match known prefix patterns like "HR REGIONAL", "PS CENTRAL"
    prefix_pattern = r'\b(' + '|'.join(_HOSPITAL_PREFIXES) + r')\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+)*)'
    for match in re.finditer(prefix_pattern, text, re.IGNORECASE):
        full = match.group(0).strip()
        keywords.append(full)
    
    # Strategy 2: Look for words after "en", "de", "del", "in", "from" 
    # (location prepositions). Support multi-word locations with inner prepositions like "San Juan del Sur".
    prep_pattern = r'\b(?:en|de|del|in|from)\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+(?:de|del|el|la|los|las|y)\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)*)'
    for match in re.finditer(prep_pattern, text):
        candidate = match.group(1).strip()
        # Check candidate isn't a stop word or region phrase
        if not _is_region_or_department_context(candidate, text):
            words = candidate.split()
            clean_words = [w for w in words if w.lower() not in _STOP_WORDS]
            if clean_words:
                cand_str = " ".join(clean_words)
                if not _is_region_or_department_context(cand_str, text):
                    keywords.append(cand_str)
    
    # Strategy 3: Look for standalone capitalized words (proper nouns)
    # that aren't at the start of the sentence
    words = text.split()
    for i, word in enumerate(words):
        clean = re.sub(r'[^\w]', '', word)
        if not clean:
            continue
        if clean[0].isupper() and i > 0 and clean.lower() not in _STOP_WORDS:
            if len(clean) > 2 and not _is_region_or_department_context(clean, text):  # Skip short words like "El", "La"
                keywords.append(clean)
    
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for kw in keywords:
        lower = kw.lower()
        if lower not in seen:
            seen.add(lower)
            unique.append(kw)
    
    return unique


def find_matching_hospitals(
    query: str,
    pg_config: dict,
) -> tuple[list[str], str]:
    """
    Search the establecimiento table for hospitals matching keywords in the query.
    
    Returns:
        Tuple of (list of matching hospital names, the keyword that was searched)
    """
    keywords = _extract_location_keywords(query)
    
    if not keywords:
        return [], ""
    
    # Try each keyword until we find matches
    for keyword in keywords:
        try:
            conn = psycopg2.connect(**pg_config, options="-c statement_timeout=5000")
            try:
                with conn.cursor() as cur:
                    # Search for hospitals matching this keyword
                    cur.execute(
                        """
                        SELECT DISTINCT nombre_establecimiento
                        FROM public.establecimiento
                        WHERE nombre_establecimiento ILIKE %s
                        ORDER BY nombre_establecimiento
                        LIMIT 10
                        """,
                        (f"%{keyword}%",),
                    )
                    results = [row[0].strip() for row in cur.fetchall() if row[0]]
                    
                    if results:
                        logger.info(
                            "Hospital disambiguation: keyword='%s' found %d matches: %s",
                            keyword, len(results), results,
                        )
                        return results, keyword
            finally:
                conn.close()
        except Exception as e:
            logger.error("Hospital disambiguation DB error: %s", e)
            return [], keyword
    
    return [], keywords[0] if keywords else ""


async def ask_user_to_disambiguate(
    matches: list[str],
    keyword: str,
    timeout: int = 90,
) -> Optional[str]:
    """
    Presents a numbered list for the user to select the correct hospital via a text input box.
    """
    if len(matches) == 1:
        return matches[0]
        
    content = f"Encontré varias coincidencias para '{keyword}'. ¿A cuál te refieres? (Responde con el número o el nombre)\n\n"
    for i, match in enumerate(matches, 1):
        content += f"{i}. {match}\n"
    
    content += f"\n{len(matches) + 1}. Buscar en todos (Saltar)"
    
    res = await cl.AskUserMessage(
        content=content,
        timeout=timeout,
    ).send()
    
    if res and res.get("output"):
        user_reply = res["output"].strip()
        
        # 1. Try to match by number
        if user_reply.isdigit():
            idx = int(user_reply) - 1
            if 0 <= idx < len(matches):
                return matches[idx]
            elif idx == len(matches):
                return "__ALL__"
                
        # 2. Try to match by "skip" keywords
        user_reply_lower = user_reply.lower()
        if user_reply_lower in ["buscar en todos", "saltar", "todos"]:
            return "__ALL__"
            
        # 3. Try to match by name (partial or exact)
        for match in matches:
            if user_reply_lower in match.lower():
                return match
                
        # Fallback if no match found
        return "__ALL__"
        
    # Timeout fallback
    return "__ALL__"

def _get_distinct_ilike_matches(col_name: str, ilike_pattern: str, sql: str, pg_config: dict) -> list[str]:
    """
    Find the table for a column and execute a DISTINCT query to get matches.
    """
    try:
        conn = psycopg2.connect(**pg_config, options="-c statement_timeout=5000")
        with conn.cursor() as cur:
            # Clean col_name (remove quotes)
            clean_col = col_name.strip('"').lower()
            
            # Find which tables contain this column
            cur.execute("""
                SELECT table_schema, table_name 
                FROM information_schema.columns 
                WHERE column_name = %s AND table_schema IN ('public', 'dbt_analytics')
            """, (clean_col,))
            tables = cur.fetchall()
            
            if not tables:
                return []
                
            # Heuristic: filter to tables actually mentioned in the SQL query text
            valid_tables = []
            sql_lower = sql.lower()
            for schema, tbl in tables:
                if tbl.lower() in sql_lower:
                    valid_tables.append((schema, tbl))
            
            # If our heuristic filtered out everything (maybe aliased without full name?),
            # fallback to all tables
            if not valid_tables:
                valid_tables = tables
                
            # Pick the most likely table (the first one)
            schema, tbl = valid_tables[0]
            
            # Execute the DISTINCT query to find matches
            # Using LIMIT 10 so we don't present too many options and don't overwhelm the DB
            query = f"SELECT DISTINCT {col_name} FROM {schema}.{tbl} WHERE {col_name} ILIKE %s LIMIT 10"
            cur.execute(query, (ilike_pattern,))
            results = [row[0] for row in cur.fetchall() if row[0] is not None]
            
            return results
    except Exception as e:
        logger.error(f"Error fetching distinct ILIKE matches for {col_name}: {e}")
        return []
    finally:
        if 'conn' in locals() and conn:
            conn.close()

async def process_ilike_in_sql(sql: str, pg_config: dict) -> str:
    """
    Find all ILIKE clauses in the generated SQL.
    For each clause, query the DB for matching options.
    If multiple options exist, prompt the user.
    Replaces the ILIKE clause with an exact match '='.
    """
    # Regex breakdown:
    # Group 1: The full column expression (e.g. "p.nombre_paciente" or "nombre")
    # Group 2: The table alias if present (e.g. "p.")
    # Group 3: The actual column name (e.g. "nombre_paciente")
    # Group 4: The pattern inside single quotes (e.g. "%Juan%")
    pattern = r'(([a-zA-Z0-9_"]+\.)?([a-zA-Z0-9_"]+))\s+ILIKE\s+\'([^\']+)\''
    
    # We use finditer to get all matches
    matches = list(re.finditer(pattern, sql, re.IGNORECASE))
    
    if not matches:
        return sql
        
    modified_sql = sql
    
    for match in matches:
        full_match = match.group(0)
        col_expr = match.group(1)
        col_name = match.group(3)
        ilike_pattern = match.group(4)
        
        logger.info(f"Detected ILIKE in SQL on column '{col_name}' with pattern '{ilike_pattern}'")
        
        # Run DB query in a background thread
        db_matches = await asyncio.to_thread(
            _get_distinct_ilike_matches, col_name, ilike_pattern, sql, pg_config
        )
        
        if len(db_matches) > 1:
            keyword = ilike_pattern.replace('%', '')
            logger.info(f"Multiple matches ({len(db_matches)}) found for '{keyword}'. Prompting user.")
            
            selected = await ask_user_to_disambiguate(db_matches, keyword)
            
            if selected and selected != "__ALL__":
                # Escape single quotes in selected value for SQL
                selected_escaped = selected.replace("'", "''")
                replacement = f"{col_expr} = '{selected_escaped}'"
                modified_sql = modified_sql.replace(full_match, replacement)
                logger.info(f"Replaced ILIKE with exact match: {replacement}")
                
        elif len(db_matches) == 1:
            logger.info(f"Single match found for '{ilike_pattern}': '{db_matches[0]}'. Silently replacing.")
            selected_escaped = db_matches[0].replace("'", "''")
            replacement = f"{col_expr} = '{selected_escaped}'"
            modified_sql = modified_sql.replace(full_match, replacement)
            
    return modified_sql
