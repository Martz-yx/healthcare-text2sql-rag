import asyncio
import json
import logging
import os
import time

import asyncpg
import chainlit as cl
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.server import app as chainlit_app
from starlette.responses import JSONResponse
from fastapi.responses import HTMLResponse

from engine import Text2SQLEngine
from llm import collect_small_brain, stream_small_brain, collect_big_brain, stream_big_brain, SMALL_BRAIN_MODEL, BIG_BRAIN_MODEL
from disambiguate import find_matching_hospitals, ask_user_to_disambiguate, process_ilike_in_sql
from nodes import (
    classify_intent,
    parse_question_domain,
    build_sql_prompt,
    extract_and_validate_sql,
    parse_feedback_action,
    classify_complexity,
)
from prompts import (
    SYSTEM_GENERAL_ANSWER,
    SYSTEM_CLASSIFY_FEEDBACK,
    SYSTEM_FORMAT_RESPONSE,
    SYSTEM_REWRITE_QUESTION,
    SYSTEM_CORRECT_SQL,
)
from reasoning import ReasoningFilter
from auth import auth_callback  # noqa: F401 — registers @cl.password_auth_callback
from cache import get_from_cache, add_to_cache

@cl.action_callback("select_hospital")
async def on_action_select_hospital(action: cl.Action):
    # This dummy callback is required by Chainlit so the UI doesn't throw 
    # 'Action not found' when clicking a button from AskActionMessage.
    pass

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("text2sql")

MAX_HISTORY_TURNS = int(os.getenv("MAX_HISTORY_TURNS", "10"))
DEBUG_CHAT = os.getenv("DEBUG_CHAT", "false").lower() == "true"

SMALL_BRAIN = "Small Brain"
BIG_BRAIN = "Big Brain"

# ---------------------------------------------------------------------------
# Data layer for conversation persistence
# ---------------------------------------------------------------------------

_chainlit_db_url = os.getenv(
    "CHAINLIT_DB_URL",
    "postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}".format(
        user=os.getenv("CHAINLIT_DB_USER", "chainlit"),
        password=os.getenv("CHAINLIT_DB_PASSWORD", "changeme"),
        host=os.getenv("CHAINLIT_DB_HOST", "chainlit-db"),
        port=os.getenv("CHAINLIT_DB_PORT", "5432"),
        dbname=os.getenv("CHAINLIT_DB_NAME", "chainlit"),
    ),
)


class MonitoredDataLayer(SQLAlchemyDataLayer):
    """SQLAlchemy data layer that turns conversation deletion into a soft delete.

    The UI delete works as users expect — the thread disappears from their sidebar and
    stays gone on reload — but nothing is removed from the database. Instead the thread
    is flagged ``metadata.deleted = true`` and simply filtered out of the per-user
    listing, so all threads/steps/messages remain intact for monitoring and audit.
    """

    async def delete_thread(self, thread_id: str):
        logger.info(
            "Soft-deleting thread %s — hidden from user, retained in DB for monitoring.",
            thread_id,
        )
        await self.execute_sql(
            query=(
                'UPDATE threads '
                'SET "metadata" = COALESCE("metadata", \'{}\'::jsonb) '
                "|| jsonb_build_object('deleted', true, 'deletedAt', NOW()) "
                'WHERE "id" = :id'
            ),
            parameters={"id": thread_id},
        )

    async def get_all_user_threads(self, user_id=None, thread_id=None):
        threads = await super().get_all_user_threads(
            user_id=user_id, thread_id=thread_id
        )
        if threads is None:
            return None
        # Hide soft-deleted threads from the user's sidebar and search; the rows stay
        # in the DB. Fetching a specific thread by id (monitoring/resume) is unaffected.
        return [t for t in threads if not (t.get("metadata") or {}).get("deleted")]


@cl.data_layer
def get_data_layer():
    return MonitoredDataLayer(conninfo=_chainlit_db_url)


# ---------------------------------------------------------------------------
# Feedback persistence (Chainlit PostgreSQL)
# ---------------------------------------------------------------------------

_feedback_dsn = "postgresql://{user}:{password}@{host}:{port}/{dbname}".format(
    user=os.getenv("CHAINLIT_DB_USER", "chainlit"),
    password=os.getenv("CHAINLIT_DB_PASSWORD", "changeme"),
    host=os.getenv("CHAINLIT_DB_HOST", "chainlit-db"),
    port=os.getenv("CHAINLIT_DB_PORT", "5432"),
    dbname=os.getenv("CHAINLIT_DB_NAME", "chainlit"),
)


async def _save_feedback(question: str, sql_query: str, feedback: str, username: str | None = None):
    conn = await asyncpg.connect(_feedback_dsn)
    try:
        await conn.execute(
            "INSERT INTO sql_feedback (question, sql_query, feedback, username) VALUES ($1, $2, $3, $4)",
            question, sql_query, feedback, username,
        )
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# FEAT-02: Admin Dashboard & Metrics API
# ---------------------------------------------------------------------------

@chainlit_app.get("/api/admin/stats")
async def admin_stats():
    conn = await asyncpg.connect(_feedback_dsn)
    try:
        positive = await conn.fetchval("SELECT COUNT(*) FROM sql_feedback WHERE feedback = 'positive'")
        negative = await conn.fetchval("SELECT COUNT(*) FROM sql_feedback WHERE feedback = 'negative'")
        total = await conn.fetchval("SELECT COUNT(*) FROM sql_feedback")
        total_threads = await conn.fetchval("SELECT COUNT(*) FROM threads")
        
        return JSONResponse({
            "status": "ok",
            "feedback": {
                "positive": positive,
                "negative": negative,
                "total": total
            },
            "threads": total_threads
        })
    except Exception as e:
        logger.error(f"Error fetching admin stats: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# Engine — initialized at import time, before Chainlit starts serving
# ---------------------------------------------------------------------------


def _create_engine() -> Text2SQLEngine:
    return Text2SQLEngine(
        pg_host=os.getenv("PG_HOST", "localhost"),
        pg_port=int(os.getenv("PG_PORT", "5432")),
        pg_dbname=os.getenv("PG_DBNAME", "postgres"),
        pg_user=os.getenv("PG_USER", "readonly_user"),
        pg_password=os.getenv("PG_PASSWORD", ""),
        chroma_path=os.getenv("CHROMA_PATH", "/data/chromadb"),
        max_context_items=int(os.environ["MAX_CONTEXT_ITEMS"]),
        max_result_rows=int(os.environ["MAX_RESULT_ROWS"]),
        max_full_ddl=int(os.environ["MAX_FULL_DDL"]),
        max_summary_ddl=int(os.environ["MAX_SUMMARY_DDL"]),
    )


def _run_startup_sync(engine: Text2SQLEngine):
    seed_on = os.getenv("SEED_ON_STARTUP", "true").lower() == "true"
    auto_train = os.getenv("AUTO_TRAIN_ON_STARTUP", "false").lower() == "true"

    if not seed_on and not auto_train:
        return

    sync_start = time.time()
    logger.info("=" * 60)
    logger.info("STARTUP SYNC: beginning training sequence")
    logger.info("=" * 60)

    if auto_train:
        logger.info("[1/2] AUTO-TRAIN: reading information_schema...")
        phase_start = time.time()
        try:
            count = engine.train_from_information_schema()
            elapsed = time.time() - phase_start
            logger.info("[1/2] AUTO-TRAIN: done — %d tables synced (%.1fs)", count, elapsed)
        except Exception:
            logger.exception("[1/2] AUTO-TRAIN: FAILED (service is still running)")
    else:
        logger.info("[1/2] AUTO-TRAIN: skipped")

    if seed_on:
        logger.info("[2/2] SEED SYNC: seeding dbt models...")
        try:
            from seed_dbt import seed_dbt_models
            seed_dbt_models()
        except Exception:
            logger.exception("[2/2] SEED SYNC: FAILED to seed dbt models")

        from seed_training import SEED_DOMAINS, collect_for

        total_domains = len(SEED_DOMAINS)
        logger.info("[2/2] SEED SYNC: syncing %d domains: %s", total_domains, ", ".join(SEED_DOMAINS))
        phase_start = time.time()

        for i, domain in enumerate(SEED_DOMAINS, 1):
            source = f"seed:{domain}"
            domain_start = time.time()
            logger.info("  [%d/%d] %s: collecting entries...", i, total_domains, source)
            try:
                sink = collect_for(domain)
                logger.info(
                    "  [%d/%d] %s: collected %d DDLs, %d docs, %d Q&A — syncing...",
                    i, total_domains, source, len(sink.ddls), len(sink.docs), len(sink.qa),
                )
                result = engine.train_seed_batch(source, sink.ddls, sink.docs, sink.qa)
                elapsed = time.time() - domain_start
                skipped = all(
                    result.get(col, {}).get("skipped", False)
                    for col in ("ddl", "documentation", "question_sql")
                )
                if skipped:
                    logger.info("  [%d/%d] %s: no changes, skipped (%.1fs)", i, total_domains, source, elapsed)
                else:
                    logger.info("  [%d/%d] %s: done (%.1fs) — %s", i, total_domains, source, elapsed, result)
            except Exception:
                elapsed = time.time() - domain_start
                logger.exception("  [%d/%d] %s: FAILED after %.1fs", i, total_domains, source, elapsed)

        phase_elapsed = time.time() - phase_start
        logger.info("[2/2] SEED SYNC: all domains done (%.1fs)", phase_elapsed)
    else:
        logger.info("[2/2] SEED SYNC: skipped")

    total_elapsed = time.time() - sync_start
    health = engine.health_check()
    training = health["training"]
    logger.info("=" * 60)
    logger.info(
        "STARTUP SYNC: complete (%.1fs) — %d DDLs, %d docs, %d Q&A, %d catalog tables",
        total_elapsed,
        training["ddl_count"],
        training["documentation_count"],
        training["question_sql_count"],
        training["catalog_tables"],
    )
    logger.info("=" * 60)


logger.info("Initializing Text-to-SQL engine...")
_engine = _create_engine()
logger.info("Engine health: %s", _engine.health_check())
_run_startup_sync(_engine)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@chainlit_app.get("/health")
async def health():
    result = _engine.health_check()
    ok = all(result["status"].values())
    return JSONResponse(result, status_code=200 if ok else 503)


# ---------------------------------------------------------------------------
# Conversation history helper
# ---------------------------------------------------------------------------


def _get_history(max_turns: int = MAX_HISTORY_TURNS) -> list[dict]:
    all_messages = cl.chat_context.to_openai()
    limit = max_turns * 2
    if len(all_messages) > limit:
        return all_messages[-limit:]
    return list(all_messages)


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Pacientes de hoy",
            message="¿Cuántos pacientes se atendieron hoy?",
        ),
        cl.Starter(
            label="Top diagnósticos",
            message="Muéstrame el top 10 de diagnósticos de este mes",
        ),
        cl.Starter(
            label="Camas disponibles",
            message="¿Cuántas camas disponibles hay por hospital?",
        ),
        cl.Starter(
            label="Medicamentos comunes",
            message="¿Cuáles fueron los medicamentos más recetados esta semana?",
        )
    ]

@cl.on_chat_start
async def on_chat_start():
    cl.user_session.set("awaiting_feedback", False)
    cl.user_session.set("last_sql", "")
    cl.user_session.set("last_question", "")


@cl.on_chat_resume
async def on_chat_resume(thread):
    cl.user_session.set("awaiting_feedback", False)
    cl.user_session.set("last_sql", "")
    cl.user_session.set("last_question", "")


# ---------------------------------------------------------------------------
# Main message handler
# ---------------------------------------------------------------------------


@cl.on_message
async def on_message(message: cl.Message):
    user_text = message.content.strip()
    
    export_excel = False
    viz_type = None
    
    if "[--export-excel]" in user_text:
        export_excel = True
        user_text = user_text.replace("[--export-excel]", "").strip()
        
    if "[--viz-bar]" in user_text or "[--viz]" in user_text:
        viz_type = "auto"
        user_text = user_text.replace("[--viz-bar]", "").replace("[--viz]", "").strip()
        
        text_lower = user_text.lower()
        if any(w in text_lower for w in ["torta", "circular", "pastel", "pie"]):
            viz_type = "pie"
        elif any(w in text_lower for w in ["linea", "línea", "tendencia", "evolucion", "evolución", "line"]):
            viz_type = "line"
        elif any(w in text_lower for w in ["barra", "barras", "bar"]):
            viz_type = "bar"
        elif any(w in text_lower for w in ["dispersion", "dispersión", "scatter", "puntos"]):
            viz_type = "scatter"

    if export_excel or viz_type:
        message.content = user_text
        await message.update()

    if not user_text:
        return

    engine = _engine
    awaiting_feedback = cl.user_session.get("awaiting_feedback")
    
    current_user = cl.user_session.get("user")
    user_role = current_user.metadata.get("role", "").lower() if current_user else ""
    is_admin = user_role == "admin"
    show_steps = is_admin or DEBUG_CHAT

    # ---- Feedback branch ----
    if awaiting_feedback:
        cl.user_session.set("awaiting_feedback", False)

        feedback_response = await collect_small_brain(
            system_prompt=SYSTEM_CLASSIFY_FEEDBACK,
            user_message=user_text,
        )
        action = parse_feedback_action(feedback_response)

        username = None
        if cl.user_session.get("user"):
            username = cl.user_session.get("user").identifier

        if action == "confirm":
            last_q = cl.user_session.get("last_question")
            last_s = cl.user_session.get("last_sql")
            if last_q and last_s:
                await _save_feedback(last_q, last_s, "positive", username)
            await cl.Message(content="¡Gracias! La consulta fue guardada para mejorar futuras respuestas.").send()
            return

        if action == "deny":
            last_q = cl.user_session.get("last_question")
            last_s = cl.user_session.get("last_sql")
            if last_q and last_s:
                await _save_feedback(last_q, last_s, "negative", username)
            await cl.Message(content="Entendido, la consulta no será guardada para entrenamiento.").send()
            return

        if action == "confirm_and_continue":
            last_q = cl.user_session.get("last_question")
            last_s = cl.user_session.get("last_sql")
            if last_q and last_s:
                await _save_feedback(last_q, last_s, "positive", username)
            await cl.Message(content="¡Gracias! La consulta fue guardada. Procesando tu nueva pregunta...").send()

        elif action == "deny_and_continue":
            last_q = cl.user_session.get("last_question")
            last_s = cl.user_session.get("last_sql")
            if last_q and last_s:
                await _save_feedback(last_q, last_s, "negative", username)
            await cl.Message(content="Entendido. Procesando tu nueva pregunta...").send()

    # ---- Intent classification ----
    t0 = time.time()
    intent_result = await classify_intent(user_text, _get_history())
    logger.info("[TIMING] classify_intent: %.2fs", time.time() - t0)

    # ---- General conversation ----
    if not intent_result["is_database_query"]:
        if show_steps:
            async with cl.Step(name=SMALL_BRAIN, type="undefined") as llm_step:
                llm_step.output = f"Model Used: {SMALL_BRAIN}"
                if DEBUG_CHAT:
                    llm_step.output += f"\nLLM: {SMALL_BRAIN_MODEL}"

        history = _get_history()
        msg = cl.Message(content="")
        await msg.send()

        reasoning_filter = ReasoningFilter(strip_think=not show_steps)
        async for chunk in stream_small_brain(
            system_prompt=SYSTEM_GENERAL_ANSWER,
            user_message=user_text,
            history=history,
        ):
            filtered = reasoning_filter.process(chunk)
            if filtered:
                await msg.stream_token(filtered)

        tail = reasoning_filter.flush()
        if tail:
            await msg.stream_token(tail)
        await msg.update()
        return

    # ---- Database query pipeline ----
    pipeline_start = time.time()
    history = _get_history()

    # Step 1: Rewrite question + classify domain (thinking disabled)
    t0 = time.time()
    rewrite_response = await collect_big_brain(
        system_prompt=SYSTEM_REWRITE_QUESTION,
        user_message=user_text,
        history=history,
        thinking=False,
    )
    logger.info("[TIMING] rewrite: %.2fs", time.time() - t0)
    parsed = parse_question_domain(rewrite_response)
    rewritten_question = parsed["pregunta"]
    domain = parsed["dominio"]

    # Step 1.5: Hospital disambiguation
    try:
        hospital_matches, hospital_keyword = await asyncio.to_thread(
            find_matching_hospitals, user_text, engine.pg_config,
        )
        if len(hospital_matches) > 1:
            selected = await ask_user_to_disambiguate(hospital_matches, hospital_keyword)
            if selected and selected != "__ALL__":
                import re as _re
                rewritten_question = _re.sub(
                    _re.escape(hospital_keyword),
                    selected,
                    rewritten_question,
                    flags=_re.IGNORECASE,
                    count=1,
                )
                logger.info(
                    "Disambiguated hospital: '%s' -> '%s' in question: %s",
                    hospital_keyword, selected, rewritten_question,
                )
        elif len(hospital_matches) == 1:
            exact_name = hospital_matches[0]
            if hospital_keyword.lower() != exact_name.lower():
                from disambiguate import _HOSPITAL_PREFIXES
                kw_has_prefix = any(hospital_keyword.upper().startswith(p + " ") for p in _HOSPITAL_PREFIXES)
                exact_starts_with_kw = exact_name.lower().startswith(hospital_keyword.lower())

                if kw_has_prefix or exact_starts_with_kw:
                    import re as _re
                    rewritten_question = _re.sub(
                        _re.escape(hospital_keyword),
                        exact_name,
                        rewritten_question,
                        flags=_re.IGNORECASE,
                        count=1,
                    )
                    logger.info(
                        "Auto-resolved hospital: '%s' -> '%s'",
                        hospital_keyword, exact_name,
                    )
                else:
                    logger.info(
                        "Skipping auto-resolve for keyword '%s' matching '%s' (not explicit hospital prefix/prefix match)",
                        hospital_keyword, exact_name,
                    )
    except Exception as e:
        logger.error("Error during hospital disambiguation: %s", e, exc_info=True)
        # Continue silently with the original rewritten_question

    # Check cache using the rewritten question
    cached_entry = get_from_cache(rewritten_question, domain=domain, embedding_fn=engine._embedding_fn)
    if cached_entry:
        if show_steps:
            async with cl.Step(name="Cache", type="undefined") as cache_step:
                cache_step.output = (
                    f"Cache Hit: similar to '{cached_entry.rewritten_question}'\n"
                    f"Domain: {cached_entry.domain}\n"
                    f"SQL: {cached_entry.sql}"
                )
        
        answer_msg = cl.Message(content="")
        await answer_msg.send()
        await answer_msg.stream_token(cached_entry.formatted_answer)
        await answer_msg.stream_token(
            "\n\n---\n\n"
            "*¿El resultado es correcto?* Responda **sí** o **no** para ayudar a mejorar el sistema."
        )
        await answer_msg.update()
        
        cl.user_session.set("awaiting_feedback", True)
        cl.user_session.set("last_sql", cached_entry.sql)
        cl.user_session.set("last_question", cached_entry.rewritten_question)
        logger.info("[TIMING] total_pipeline (cached hit): %.2fs", time.time() - pipeline_start)
        return

    # Routing + domain
    domain_labels = {
        "ambulatoria": "Consultas externas",
        "internacion": "Internación",
        "ambos": "Ambulatoria + Internación",
    }
    if show_steps:
        async with cl.Step(name=BIG_BRAIN, type="undefined") as route_step:
            route_step.output = (
                f"Model Used: {BIG_BRAIN}\n"
                f"Task: Rewrite + Domain Classification (no thinking)\n"
                f"Dominio: {domain_labels.get(domain, domain)}"
            )
            if DEBUG_CHAT:
                route_step.output += f"\nLLM: {BIG_BRAIN_MODEL}"

        async with cl.Step(name="Rewrite", type="undefined") as rewrite_step:
            rewrite_step.output = (
                f"Model: {BIG_BRAIN_MODEL}\n"
                f"Pregunta: {rewritten_question}"
            )

    start_time = time.time()
    
    phases_verbs = {
        "Pensando": "Pensado",
        "Consultando a la base de datos": "Consultado",
        "Finalizado": "Finalizado"
    }

    current_phase_name = "Pensando"
    phase_start_time = time.time()
    global_start_time = time.time()
    
    def format_time(seconds):
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s" if m > 0 else f"{s}s"

    def build_shimmer_html(phase, seconds):
        return f"""
<div style="margin-bottom: 4px; font-weight: 500; font-size: 0.9em; opacity: 0.7;">
    {phase}... {format_time(seconds)}
</div>
<div class="shimmer-container">
    <div class="shimmer-line long"></div>
    <div class="shimmer-line short"></div>
</div>
"""

    current_msg = cl.Message(content=build_shimmer_html(current_phase_name, 0), author="HIS_Thinking")
    await current_msg.send()



    async def switch_phase(new_name):
        nonlocal current_phase_name, phase_start_time, current_msg
        now = time.time()
        
        if show_steps:
            dur = int(now - phase_start_time)
            past_verb = phases_verbs.get(current_phase_name, current_phase_name)
            current_msg.content = f"<span style='opacity: 0.5; font-style: italic;'>{past_verb} ({format_time(dur)})</span>"
            current_msg.author = "HIS_Done"
            await current_msg.update()
            
            current_phase_name = new_name
            phase_start_time = now
            
            if new_name != "Finalizado":
                current_msg = cl.Message(content=build_shimmer_html(current_phase_name, 0), author="HIS_Thinking")
                await current_msg.send()
        else:
            if new_name == "Finalizado":
                await current_msg.remove()
            else:
                current_phase_name = new_name

    stop_timer = asyncio.Event()

    async def ticker():
        while not stop_timer.is_set():
            now = time.time()
            if show_steps:
                elapsed = int(now - phase_start_time)
            else:
                elapsed = int(now - global_start_time)
                
            current_msg.content = build_shimmer_html(current_phase_name, elapsed)
            try:
                await current_msg.update()
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop_timer.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

    async def finish_timer():
        stop_timer.set()
        await ticker_task
        await switch_phase("Finalizado")

    ticker_task = asyncio.create_task(ticker())

    # RAG context
    t0 = time.time()
    context = await asyncio.to_thread(engine.retrieve_context, rewritten_question, domain)
    logger.info("[TIMING] rag_context: %.2fs", time.time() - t0)

    if show_steps:
        async with cl.Step(name="RAG Context", type="undefined") as ctx_step:
            ctx_step.output = (
                f"{len(context.get('ddl', []))} DDLs, "
                f"{len(context.get('documentation', []))} docs, "
                f"{len(context.get('question_sql', []))} examples"
            )

    # Generate SQL (streamed into a Message so the user sees progress)
    system_prompt = build_sql_prompt(context)
    prompt_chars = len(system_prompt)
    logger.info("SQL system prompt size: %d chars (~%d tokens)", prompt_chars, prompt_chars // 4)

    if show_steps:
        async with cl.Step(name="System Prompt", type="undefined") as prompt_step:
            prompt_step.output = f"Chars: {prompt_chars} (~{prompt_chars // 4} tokens)\n```\n{system_prompt}\n```"

    # Complexity classification
    t0 = time.time()
    is_complex = await classify_complexity(rewritten_question, history)
    logger.info("[TIMING] classify_complexity: %.2fs (is_complex=%s)", time.time() - t0, is_complex)
    
    if show_steps:
        async with cl.Step(name="Clasificación de Complejidad", type="undefined") as complex_step:
            complex_step.output = f"Model: {SMALL_BRAIN_MODEL}\nComplejidad: {'Alta (Thinking Activo)' if is_complex else 'Baja (Thinking Desactivado)'}"

    # Timer keeps running during execution


    sql_result = None
    exec_result = None
    
    max_attempts = 2
    for attempt in range(max_attempts):
        is_retry = attempt > 0
        if is_retry:
            await switch_phase("Pensando (Reintento)")
            
            retry_prompt = SYSTEM_CORRECT_SQL.format(
                question=rewritten_question,
                failed_sql=sql_result["sql"] if sql_result and "sql" in sql_result else "N/A",
                error=exec_result.error if exec_result else sql_result["error"] if sql_result else "Unknown Error",
                schema_context=system_prompt
            )
            
            if show_steps:
                async with cl.Step(name="Corrección SQL (Retry)", type="undefined") as retry_step:
                    err_msg = exec_result.error if exec_result else sql_result['error'] if sql_result else "Unknown Error"
                    retry_step.output = f"Model: {BIG_BRAIN_MODEL}\nIntentando corregir error: {err_msg}"
                    
        t0 = time.time()
        sql_chunks: list[str] = []
        reasoning_filter_sql = ReasoningFilter(strip_think=not show_steps)
        
        sql_msg = None
        sql_debug_parts: list[str] = []
        if show_steps:
            sql_msg = cl.Step(name=f"Razonamiento y Generación SQL{' (Retry)' if is_retry else ''}", type="undefined")
            await sql_msg.send()
        
        async for chunk in stream_big_brain(
            system_prompt=retry_prompt if is_retry else system_prompt,
            user_message=rewritten_question,
            history=history if not is_retry else [],
            thinking=True if is_retry else is_complex,
        ):
            sql_chunks.append(chunk)
            filtered = reasoning_filter_sql.process(chunk)
            if filtered and sql_msg is not None:
                sql_debug_parts.append(filtered)
                await sql_msg.stream_token(filtered)
        tail_sql = reasoning_filter_sql.flush()
        if tail_sql and sql_msg is not None:
            sql_debug_parts.append(tail_sql)
            await sql_msg.stream_token(tail_sql)
        if sql_msg is not None:
            sql_msg.output = "".join(sql_debug_parts)
            await sql_msg.update()

        sql_response = "".join(sql_chunks)
        logger.info("[TIMING] sql_generation (attempt %d): %.2fs", attempt + 1, time.time() - t0)
        sql_result = extract_and_validate_sql(sql_response)

        if show_steps:
            async with cl.Step(name=f"SQL{' (Retry)' if is_retry else ''}", type="undefined") as sql_step:
                if sql_result["is_valid"]:
                    sql_step.output = f"Model: {BIG_BRAIN_MODEL}\n```sql\n{sql_result['sql']}\n```"
                else:
                    sql_step.output = f"Model: {BIG_BRAIN_MODEL}\nError: {sql_result['error']}"

        if not sql_result["is_valid"]:
            if attempt == max_attempts - 1:
                await finish_timer()
                
                error_content = (
                    "Lo siento, no pude generar una consulta válida para esa pregunta.\n\n"
                    f"**Motivo:** {sql_result['error']}\n\n"
                )
                
                from nodes import suggest_reformulation
                try:
                    sugerencia = await suggest_reformulation(user_text, sql_result["error"])
                    error_content += f"**Sugerencia:** {sugerencia}"
                except Exception as e:
                    logger.error(f"Error generando sugerencia: {e}")
                    error_content += "Intente reformular su pregunta o proporcionar más detalles."
                
                await cl.Message(content=error_content).send()
                return
            else:
                continue

        # Process any ILIKE statements in the valid SQL before execution
        try:
            final_sql = await process_ilike_in_sql(sql_result["sql"], engine.pg_config)
            
            # If the SQL changed, log the change and update the valid SQL
            if final_sql != sql_result["sql"]:
                if show_steps:
                    async with cl.Step(name=f"SQL Desambiguado{' (Retry)' if is_retry else ''}", type="undefined") as dis_step:
                        dis_step.output = f"```sql\n{final_sql}\n```"
                sql_result["sql"] = final_sql
        except Exception as e:
            logger.error(f"Error during ILIKE disambiguation: {e}", exc_info=True)
            # Proceed with original SQL if error occurs

        # Execute SQL
        await switch_phase("Consultando a la base de datos")
        t0 = time.time()
        exec_result = await asyncio.to_thread(engine.execute_validated, sql_result["sql"])
        logger.info("[TIMING] sql_execution (attempt %d): %.2fs", attempt + 1, time.time() - t0)

        if show_steps:
            async with cl.Step(name=f"Ejecución{' (Retry)' if is_retry else ''}", type="undefined") as exec_step:
                if exec_result.error:
                    exec_step.output = f"Error: {exec_result.error}"
                else:
                    exec_step.output = f"{exec_result.row_count} filas"

        if exec_result.error:
            if attempt == max_attempts - 1:
                await finish_timer()
                error_content = f"Error al ejecutar la consulta: {exec_result.error}"
                if DEBUG_CHAT:
                    error_content += f"\n\n```sql\n{exec_result.sql}\n```"
                
                from nodes import suggest_reformulation
                try:
                    sugerencia = await suggest_reformulation(user_text, exec_result.error)
                    error_content += f"\n\n**Sugerencia:** {sugerencia}"
                except Exception as e:
                    logger.error(f"Error generando sugerencia: {e}")
                
                await cl.Message(content=error_content).send()
                return
            else:
                continue
                
        # If we reach here, execution was successful
        break

    await finish_timer()

    # Format results (streamed)

    if show_steps:
        async with cl.Step(name=SMALL_BRAIN, type="undefined") as fmt_route:
            fmt_route.output = f"Model Used: {SMALL_BRAIN}\nTask: Format Response"
            if DEBUG_CHAT:
                fmt_route.output += f"\nLLM: {SMALL_BRAIN_MODEL}"

    actual_results = exec_result.results or []
    if len(actual_results) > 100:
        export_excel = True
        viz_type = None
        sample_results = actual_results[:5]
        results_json = json.dumps(sample_results, indent=2, default=str) + f"\n... (y {len(actual_results) - 5} filas más omitidas. Ver Excel adjunto para los datos completos.)"
    else:
        results_json = json.dumps(actual_results, indent=2, default=str)

    format_user_msg = (
        f"Pregunta del usuario: {user_text}\n"
        f"Consulta SQL utilizada: {sql_result['sql']}\n"
        f"Cantidad de filas: {exec_result.row_count}\n"
        f"Resultados: {results_json}"
    )

    answer_msg = cl.Message(content="")
    await answer_msg.send()

    formatted_chunks = []
    reasoning_filter = ReasoningFilter(strip_think=not show_steps)
    async for chunk in stream_small_brain(
        system_prompt=SYSTEM_FORMAT_RESPONSE,
        user_message=format_user_msg,
    ):
        filtered = reasoning_filter.process(chunk)
        if filtered:
            formatted_chunks.append(filtered)
            await answer_msg.stream_token(filtered)

    tail = reasoning_filter.flush()
    if tail:
        formatted_chunks.append(tail)
        await answer_msg.stream_token(tail)

    formatted_answer = "".join(formatted_chunks)

    # --- Excel and Viz Additions ---
    elements = []
    try:
        import pandas as pd
        if (export_excel or viz_type) and exec_result.results:
            df = pd.DataFrame(exec_result.results)
            
            if export_excel:
                import re
                from datetime import datetime
                os.makedirs("public/exports", exist_ok=True)
                base_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', user_text.strip()[:30])
                if not base_name:
                    base_name = "Resultados_HIS"
                timestamp = datetime.now().strftime("%d.%m.%Y_%H%MHs")
                dynamic_filename = f"{base_name}_{timestamp}.xlsx"
                file_path = f"public/exports/{dynamic_filename}"
                df.to_excel(file_path, index=False, sheet_name='Resultados')
                
                # Append the download link to the final answer message
                answer_msg.content += f"\n\n**[Descargar Excel: {dynamic_filename}](/public/exports/{dynamic_filename})**"
                await answer_msg.update()
            
            if viz_type and not df.empty:
                import plotly.express as px
                
                str_cols = df.select_dtypes(include=['object', 'string', 'category']).columns
                num_cols = df.select_dtypes(include=['number']).columns
                # Convert string columns that look like dates to datetime for better chart heuristics
                for col in str_cols:
                    try:
                        df[col] = pd.to_datetime(df[col])
                    except (ValueError, TypeError):
                        pass
                date_cols = df.select_dtypes(include=['datetime', 'datetimetz']).columns
                str_cols = df.select_dtypes(include=['object', 'string', 'category']).columns
                
                if viz_type == "auto":
                    if len(date_cols) > 0 and len(num_cols) > 0:
                        viz_type = "line"
                    elif len(str_cols) > 0 and len(num_cols) > 0:
                        unique_cats = df[str_cols[0]].nunique()
                        if unique_cats <= 5:
                            viz_type = "pie"
                        else:
                            viz_type = "bar"
                    else:
                        viz_type = "bar"
                
                fig = None
                if viz_type == "line" and (len(date_cols) > 0 or len(str_cols) > 0) and len(num_cols) > 0:
                    x_col = date_cols[0] if len(date_cols) > 0 else str_cols[0]
                    df = df.sort_values(by=x_col)
                    fig = px.line(df, x=x_col, y=num_cols[0], title=f"Evolución de {num_cols[0]}", template="plotly_dark", markers=True)
                elif viz_type == "pie" and len(str_cols) > 0 and len(num_cols) > 0:
                    fig = px.pie(df, names=str_cols[0], values=num_cols[0], title=f"Distribución de {num_cols[0]} por {str_cols[0]}", template="plotly_dark")
                elif viz_type == "scatter" and len(num_cols) >= 2:
                    fig = px.scatter(df, x=num_cols[0], y=num_cols[1], title=f"{num_cols[1]} vs {num_cols[0]}", template="plotly_dark")
                else:
                    if len(str_cols) > 0 and len(num_cols) > 0:
                        fig = px.bar(df, x=str_cols[0], y=num_cols[0], title=f"{num_cols[0]} por {str_cols[0]}", template="plotly_dark")
                    elif len(num_cols) >= 2:
                        fig = px.bar(df, x=num_cols[0], y=num_cols[1], title=f"{num_cols[1]} por {num_cols[0]}", template="plotly_dark")
                    elif len(str_cols) >= 1:
                        counts = df[str_cols[0]].value_counts().reset_index()
                        counts.columns = [str_cols[0], 'Conteo']
                        fig = px.bar(counts, x=str_cols[0], y='Conteo', title=f"Conteo de {str_cols[0]}", template="plotly_dark")
                    else:
                        fig = px.bar(x=["Total"], y=[len(df)], title="Total de Registros", template="plotly_dark")
                
                if fig:
                    fig.update_layout(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font_color='white'
                    )
                    chart = cl.Plotly(name="Visualización", figure=fig, display="inline")
                    elements.append(chart)
    except Exception as e:
        logger.error(f"Error generating Excel/Viz: {e}")

    if elements:
        answer_msg.elements = elements

    # Save to cache
    add_to_cache(
        raw_question=user_text,
        domain=domain,
        rewritten_question=rewritten_question,
        sql=sql_result["sql"],
        formatted_answer=formatted_answer,
        embedding_fn=engine._embedding_fn
    )

    await answer_msg.stream_token(
        "\n\n---\n\n"
        "*¿El resultado es correcto?* Responda **sí** o **no** para ayudar a mejorar el sistema."
    )
    await answer_msg.update()

    logger.info("[TIMING] total_pipeline: %.2fs", time.time() - pipeline_start)



    cl.user_session.set("awaiting_feedback", True)
    cl.user_session.set("last_sql", sql_result["sql"])
    cl.user_session.set("last_question", rewritten_question)
