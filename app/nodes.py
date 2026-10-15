import json
import re

from llm import collect_big_brain, collect_small_brain
from prompts import SYSTEM_CLASSIFY_INTENT, _HIS_SYSTEM_CONTEXT, SYSTEM_CLASSIFY_COMPLEXITY


async def classify_intent(query: str, history: list[dict] | None = None) -> dict:
    response = await collect_big_brain(
        system_prompt=SYSTEM_CLASSIFY_INTENT,
        user_message=query,
        history=history,
        thinking=False,
    )
    is_db = "GENERAL" not in response.strip().upper()
    return {
        "is_database_query": is_db,
        "intent": "database" if is_db else "general",
    }


async def classify_complexity(query: str, history: list[dict] | None = None) -> bool:
    response = await collect_small_brain(
        system_prompt=SYSTEM_CLASSIFY_COMPLEXITY,
        user_message=query,
        history=history,
    )
    return "COMPLEX" in response.strip().upper()


def parse_question_domain(llm_output: str) -> dict:
    text = llm_output.strip()

    dominio = "ambos"
    pregunta = ""

    dominio_match = re.search(r"DOMINIO:\s*(\S+)", text, re.IGNORECASE)
    if dominio_match:
        val = dominio_match.group(1).lower().strip()
        if val in ("ambulatoria", "internacion", "ambos"):
            dominio = val

    pregunta_match = re.search(r"PREGUNTA:\s*(.+)", text, re.IGNORECASE | re.DOTALL)
    if pregunta_match:
        pregunta = pregunta_match.group(1).strip()

    if not pregunta:
        pregunta = text

    return {"pregunta": pregunta, "dominio": dominio}


def build_sql_prompt(context: dict) -> str:
    parts = [
        "Eres un experto en PostgreSQL.",
        "Tu trabajo es generar UNA SOLA consulta SQL SELECT que responda la pregunta del usuario.",
        "IMPORTANTE: Tu respuesta SIEMPRE debe ser una consulta SQL. NUNCA respondas con texto, "
        "datos o explicaciones directamente, incluso si crees conocer la respuesta por el historial "
        "de conversacion.",
        "",
        "REGLAS ESTRICTAS:",
        "- SIEMPRE genera una consulta SQL, incluso para preguntas muy especificas o de una sola fila",
        "- NUNCA respondas con datos directamente, tu unica salida valida es un bloque ```sql o CANNOT_QUERY",
        "- Genera UNICAMENTE una consulta SELECT",
        "- NUNCA generes INSERT, UPDATE, DELETE, DROP, ALTER, CREATE ni ninguna sentencia que modifique datos",
        "- Agrega LIMIT 500 a menos que el usuario pida explicitamente sin limite o un numero especifico",
        "- Usa los nombres de tablas y columnas EXACTAMENTE como aparecen en el esquema",
        "- Si no puedes generar una consulta valida, responde UNICAMENTE con: CANNOT_QUERY: <razon>",
        "- Devuelve UNICAMENTE la consulta SQL dentro de un bloque ```sql",
        "- NO escribas explicaciones, comentarios, ni texto adicional fuera del bloque SQL",
        "- NO escribas multiples versiones de la consulta, solo UNA version final",
        "- NO uses tablas ni columnas que no estan en el esquema proporcionado",
        "- Puedes usar tablas del resumen si necesitas hacer JOINs adicionales",
        "",
        "=== CONTEXTO DEL SISTEMA Y REGLAS GENERALES ===",
        _HIS_SYSTEM_CONTEXT,
    ]

    ddl_list = context.get("ddl", [])
    if ddl_list:
        parts.append("")
        parts.append("=== ESQUEMA COMPLETO (tablas principales) ===")
        for d in ddl_list:
            parts.append(d)
            parts.append("")

    ddl_summary_list = context.get("ddl_summary", [])
    if ddl_summary_list:
        parts.append("=== OTRAS TABLAS DISPONIBLES (resumen, usar si necesario) ===")
        for s in ddl_summary_list:
            parts.append("- " + s)
        parts.append("")

    docs_list = context.get("documentation", [])
    if docs_list:
        parts.append("=== REGLAS DE NEGOCIO Y DOCUMENTACION ===")
        for d in docs_list:
            parts.append("- " + d)
        parts.append("")

    qa_list = context.get("question_sql", [])
    if qa_list:
        parts.append("=== CONSULTAS DE EJEMPLO (usar como referencia) ===")
        for q in qa_list:
            parts.append(q)
            parts.append("")

    return "\n".join(parts)


def extract_and_validate_sql(llm_response: str) -> dict:
    if not llm_response or not llm_response.strip():
        return {"sql": "", "error": "El modelo no genero una respuesta.", "is_valid": False}

    text = llm_response.strip()

    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    text = re.sub(
        r"\[Routing\].*?(?=SELECT|WITH|CANNOT_QUERY|```)",
        "", text, flags=re.DOTALL | re.IGNORECASE,
    ).strip()

    text_lower = text.lower()

    cannot_match = re.search(r"CANNOT_QUERY:\s*(.+)", text, re.IGNORECASE)
    if cannot_match:
        reason = cannot_match.group(1).strip().split("\n")[0]
        return {"sql": "", "error": reason, "is_valid": False}

    refusals = [
        "i don't know", "i cannot", "i'm not able", "i am not able",
        "not enough information", "cannot generate", "unable to generate",
        "cannot determine", "don't have enough",
        "no puedo", "no tengo suficiente", "no es posible",
    ]
    for phrase in refusals:
        if phrase in text_lower:
            return {
                "sql": "",
                "error": "No se pudo generar la consulta SQL para esta pregunta.",
                "is_valid": False,
            }

    sql_blocks = re.findall(r"```sql\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if sql_blocks:
        sql = sql_blocks[-1].strip().rstrip(";").strip()
        if sql:
            sql = sql + ";"
        else:
            return {"sql": "", "error": "Bloque SQL vacio en la respuesta.", "is_valid": False}
    else:
        code_blocks = re.findall(r"```\s*(.*?)```", text, re.DOTALL)
        if code_blocks:
            candidate = code_blocks[-1].strip().rstrip(";").strip()
            if candidate and candidate.upper().startswith(("SELECT", "WITH")):
                sql = candidate + ";"
            else:
                sql = None
        else:
            sql = None

        if not sql:
            patterns = [
                re.compile(r"(WITH\s+[\s\S]+?;)", re.IGNORECASE),
                re.compile(r"(SELECT\s+[\s\S]+?;)", re.IGNORECASE),
            ]
            for pattern in patterns:
                matches = pattern.findall(text)
                if matches:
                    sql = matches[-1].strip()
                    break

        if not sql and text_lower.startswith(("select", "with")):
            sql = text.rstrip(";").strip() + ";"

    if not sql:
        return {
            "sql": "",
            "error": "No se pudo extraer SQL de la respuesta del modelo.",
            "is_valid": False,
        }

    sql_clean = re.sub(r"--[^\n]*", "", sql)
    sql_clean = sql_clean.strip()
    if not sql_clean or not sql_clean.rstrip(";").strip():
        return {
            "sql": "",
            "error": "La consulta SQL esta vacia despues de limpiar comentarios.",
            "is_valid": False,
        }
    sql = sql_clean.rstrip(";").strip() + ";"

    sql_upper = sql.upper()

    if "SELECT" not in sql_upper:
        return {"sql": sql, "error": "La consulta no contiene SELECT.", "is_valid": False}

    dangerous = [
        "INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE ",
        "TRUNCATE ", "GRANT ", "REVOKE ", "EXEC ", "EXECUTE ",
    ]
    for kw in dangerous:
        if kw in sql_upper:
            return {
                "sql": sql,
                "error": "Bloqueado: la consulta contiene " + kw.strip(),
                "is_valid": False,
            }

    cleaned = re.sub(r"'[^']*'", "", sql)
    cleaned = re.sub(r'"[^"]*"', "", cleaned)
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(statements) > 1:
        return {"sql": sql, "error": "Se detectaron multiples sentencias SQL.", "is_valid": False}

    return {"sql": sql, "error": "", "is_valid": True}


def parse_feedback_action(llm_response: str) -> str:
    text = llm_response.strip()

    text = re.sub(r"```json?\s*", "", text)
    text = re.sub(r"```", "", text)
    text = text.strip()

    try:
        data = json.loads(text)
        feedback = data.get("feedback", "none").lower().strip()
        has_new = bool(data.get("has_new_question", False))
    except Exception:
        feedback = "none"
        has_new = True

    if feedback == "positive":
        return "confirm_and_continue" if has_new else "confirm"
    elif feedback == "negative":
        return "deny_and_continue" if has_new else "deny"
    return "new_query"

async def suggest_reformulation(query: str, db_error: str) -> str:
    prompt = (
        "Eres un asistente de ayuda para un sistema Text-to-SQL en un hospital.\n"
        "El usuario hizo una pregunta pero la generación o ejecución falló por un error técnico.\n"
        "Tu tarea es sugerir de manera AMIGABLE y BREVE (1 o 2 oraciones máximo) cómo podría reformular su pregunta usando términos correctos.\n"
        "NUNCA muestres el error técnico literal al usuario. Háblale directamente y de forma empática."
    )
    user_msg = f"Pregunta original: {query}\nError técnico: {db_error}"
    response = await collect_small_brain(
        system_prompt=prompt,
        user_message=user_msg
    )
    return response.strip()
