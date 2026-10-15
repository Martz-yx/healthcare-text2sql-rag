"""
Text-to-SQL RAG Engine

A lightweight RAG-based text-to-SQL engine that:
1. Stores DDL, documentation, and question-SQL pairs in ChromaDB
2. Retrieves relevant context via semantic similarity
3. Validates and executes SQL against PostgreSQL
4. Supports feedback-based training for continuous improvement

The LLM is managed by the Chainlit app layer (see chainlit_app.py) — this engine
handles context retrieval, SQL validation, and query execution.
"""

import re
import logging
import hashlib
from typing import Optional
from dataclasses import dataclass

import pandas as pd
import psycopg2
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

try:
    import torch
    _DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
except ImportError:
    _DEVICE = "cpu"

logger = logging.getLogger(__name__)

# Multilingual embedding model for Spanish queries matching SQL/DDL.
# BGE-M3 (568M params, 1024 dims, 8192 tokens) significantly outperforms
# paraphrase-multilingual-MiniLM-L12-v2 (118M params, 384 dims, 128 tokens)
# on multilingual retrieval benchmarks — especially for longer DDL documents
# and mixed Spanish/SQL content. Requires ~2 GB RAM vs ~0.5 GB for MiniLM.
# IMPORTANT: changing the model invalidates existing ChromaDB embeddings.
# Delete the chroma_data directory and re-seed after switching models.
EMBEDDING_MODEL = "BAAI/bge-m3"

# Seed domains. Each sync runs independently so a sweep of one domain never
# touches the other. Keep in lockstep with SEED_DOMAINS in seed_training.py.
_SEED_SOURCES = {"seed:common", "seed:ambulatoria", "seed:internacion", "seed:dbt"}

# Sources that are active (used in context retrieval).
# "user" and "feedback" entries are stored but excluded until approved.
_ACTIVE_SOURCES = _SEED_SOURCES | {"auto", "approved"}

# Max columns to include in a compact summary before truncating with "..."
_MAX_SUMMARY_COLUMNS = 15

# Critical documentation that is ALWAYS included in every context response,
# regardless of semantic similarity. Only truly cross-domain rules belong here.
# Domain-specific docs (internacion bed states, active patient filters) live in
# their seed files and reach the LLM via semantic search when relevant.
_ALWAYS_INCLUDE_DOCS = [
    (
        "RESUMEN DEL SISTEMA: Esta base de datos cubre dos dominios del Sistema de Informacion "
        "Hospitalaria (HIS): "
        "1) AMBULATORIA (consultas externas): tabla central paciente_asignacion. "
        "Cubre turnos, triaje (preconsulta), consulta medica, diagnosticos CIE-10, "
        "medicamentos, procedimientos, trauma, prescripciones a largo plazo, certificados, y agenda. "
        "Flujo: agenda -> paciente_asignacion -> preconsulta -> consulta. "
        "2) INTERNACION (hospitalizacion): tabla central hospitalario_asignacion. "
        "Cubre admisiones, camas (edificio>piso>sala>cama), evoluciones SOAP, medicaciones, "
        "cirugias, interconsultas, enfermeria NANDA-Henderson, dietas, alta/egreso, obstetricia. "
        "Filtro critico internados activos: fin_del_evento='0' AND is_outdated=false. "
        "TABLAS COMPARTIDAS: paciente, usuario, servicio, establecimiento, medicamento, cie10, "
        "via_medicine, departamento/distrito/barrio."
    ),
    (
        "NOMBRES DE PACIENTES vs MEDICOS: la tabla paciente usa primer_nombre, segundo_nombre, "
        "primer_apellido, segundo_apellido. Construir nombre: "
        "CONCAT(TRIM(p.primer_nombre), ' ', TRIM(p.primer_apellido)) AS nombre_paciente. "
        "La tabla usuario (medicos, enfermeros) usa nombres, apellidos. Construir nombre: "
        "u.nombres || ' ' || u.apellidos AS nombre_medico. "
        "Sexo del paciente: '1'=femenino, '2'=masculino."
    ),
    (
        "FECHAS Y HORAS: muchas tablas usan columnas separadas (creacion_fecha date + creacion_hora time) "
        "en lugar de timestamp. Para combinar: creacion_fecha + creacion_hora. "
        "Tablas mas nuevas usan tiempo_ejecucion (timestamp) directamente. "
        "Para filtrar por rango de fechas usar creacion_fecha BETWEEN '...' AND '...' "
        "sin combinar con hora. Usar date_trunc('month', CURRENT_DATE) para inicio de mes, "
        "make_date(extract(year from current_date)::int, 7, 1) para inicio de julio del año actual, "
        "y CURRENT_DATE para hoy. NUNCA hardcodear años pasados como 2024 o 2025 para 'este año'."
    ),

    (
        "VIGENCIA DE REGISTROS (Auditoría): Para saber si un registro es el más actual y vigente, usar las "
        "columnas isdc = 'N' o is_outdated = false. Los valores contrarios ('Y' o true) indican que "
        "son registros obsoletos de auditoría y deben ser ignorados a menos que se pidan explícitamente históricos."
    ),
    (
        "HEURISTICA DE OPTIMIZACION (AGREGADOS vs DETALLES): "
        "1) Para preguntas estadísticas de totales, sumatorias o promedios generales (ej. 'Cuantas consultas hubo', "
        "'Cuantos pacientes se atendieron en total'), SIEMPRE busca y utiliza vistas pre-agregadas que contengan la palabra "
        "'totales' (ej. mart_totales_consultas_por_tipo) y utiliza SUM() sobre sus columnas de conteo (ej. SUM(total_consultas)). "
        "2) Para buscar detalles de pacientes específicos, historiales, o cuando se pide agrupar por campos finos "
        "(ej. médico, servicio, departamento, diagnóstico exacto) que NO existen en los agregados, SIEMPRE utiliza "
        "las tablas de detalle como mart_consultas o mart_internacion y utiliza COUNT()."
    ),
    (
        "FILTROS GEOGRAFICOS Y REGIONALES: La region Capital se especifica en region o region_residencia "
        "usando region ILIKE '%CAPITAL%'. NUNCA confundir la region Capital con nombres de establecimientos "
        "locales que contienen la palabra 'CAPITAL'."
    ),
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SQLResult:
    """Result of a SQL execution."""
    sql: str
    results: Optional[list[dict]]
    row_count: int
    error: Optional[str]
    is_valid: bool


@dataclass
class TrainingEntry:
    """A single training data entry."""
    id: str
    entry_type: str  # "ddl", "documentation", "question_sql"
    content: str
    source: str  # "seed", "user", "auto"


# ---------------------------------------------------------------------------
# SQL Extraction & Validation
# ---------------------------------------------------------------------------

# Patterns for extracting SQL from LLM responses, ordered by specificity
_SQL_PATTERNS = [
    # Markdown SQL code block
    re.compile(r"```sql\s*(.*?)```", re.DOTALL | re.IGNORECASE),
    # Generic code block
    re.compile(r"```\s*(.*?)```", re.DOTALL),
    # WITH ... ; (CTE queries)
    re.compile(r"(WITH\s+[\s\S]+?;)", re.IGNORECASE),
    # SELECT ... ; (standard queries)
    re.compile(r"(SELECT\s+[\s\S]+?;)", re.IGNORECASE),
    # SELECT without trailing semicolon (fallback)
    re.compile(r"(SELECT\s+[\s\S]+)", re.IGNORECASE),
]

# Dangerous SQL keywords that should never appear in generated queries
_DANGEROUS_KEYWORDS = [
    "INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ", "CREATE ",
    "TRUNCATE ", "GRANT ", "REVOKE ", "EXEC ", "EXECUTE ",
    "INTO ", "SET ",  # catches INSERT INTO, UPDATE SET
]

# Phrases that indicate the LLM couldn't generate SQL
_REFUSAL_PHRASES = [
    "i don't know", "i cannot", "i'm not able", "i am not able",
    "not enough information", "cannot generate", "unable to generate",
    "no SQL", "cannot determine", "don't have enough",
]


def extract_sql(llm_response: str) -> Optional[str]:
    """
    Extract SQL from an LLM response, handling markdown fences,
    extra explanation text, and various formatting quirks.

    Returns None if no SQL could be extracted.
    """
    if not llm_response or not llm_response.strip():
        return None

    text = llm_response.strip()

    # Check if the LLM refused to generate SQL
    text_lower = text.lower()
    for phrase in _REFUSAL_PHRASES:
        if phrase in text_lower:
            logger.info(f"LLM refused to generate SQL: {text[:100]}")
            return None

    # Try each extraction pattern
    for pattern in _SQL_PATTERNS:
        match = pattern.search(text)
        if match:
            sql = match.group(1).strip()
            if sql:
                # Clean up: remove trailing semicolons for consistency, then add one
                sql = sql.rstrip(";").strip()
                if sql:
                    return sql + ";"

    # Last resort: if the entire response looks like SQL (starts with SELECT/WITH)
    if text_lower.startswith(("select", "with")):
        sql = text.rstrip(";").strip()
        return sql + ";" if sql else None

    return None


def validate_sql(sql: str) -> tuple[bool, Optional[str]]:
    """
    Validate that generated SQL is safe to execute.

    Returns (is_valid, error_message).
    """
    if not sql:
        return False, "Empty SQL"

    sql_upper = sql.upper()

    # Must contain SELECT
    if "SELECT" not in sql_upper:
        return False, "Query does not contain SELECT"

    # Check for dangerous operations
    for keyword in _DANGEROUS_KEYWORDS:
        # Check with word boundary awareness
        if keyword.upper() in sql_upper:
            # Exception: SELECT ... INTO is okay in subqueries context
            # but standalone INSERT INTO is not
            if keyword.strip() == "INTO":
                # Allow "INTO" only if preceded by SELECT (subquery)
                # Block if preceded by INSERT
                if "INSERT" in sql_upper:
                    return False, f"Blocked: contains INSERT INTO"
                continue
            if keyword.strip() == "SET":
                # Allow SET in OFFSET, but block UPDATE SET
                if "UPDATE" in sql_upper:
                    return False, f"Blocked: contains UPDATE SET"
                continue
            return False, f"Blocked: contains {keyword.strip()}"

    # Check for multiple statements (semicolons in the middle)
    # Remove string literals first to avoid false positives
    cleaned = re.sub(r"'[^']*'", "", sql)
    cleaned = re.sub(r'"[^"]*"', "", cleaned)
    statements = [s.strip() for s in cleaned.split(";") if s.strip()]
    if len(statements) > 1:
        return False, "Multiple SQL statements detected"

    return True, None


# ---------------------------------------------------------------------------
# DDL Parsing Helpers
# ---------------------------------------------------------------------------

def _extract_table_name_from_ddl(ddl: str) -> Optional[str]:
    """Extract the table name from a CREATE TABLE DDL statement (lowercased, no schema)."""
    match = re.search(r"CREATE\s+TABLE\s+(?:\w+\.)?(\w+)", ddl, re.IGNORECASE)
    return match.group(1).lower() if match else None


# Grab "column_name data_type" from each line inside CREATE TABLE (...)
_SIMPLE_COL_PATTERN = re.compile(
    r"^\s{2,}(\w+)\s+([\w ]+(?:\([^)]*\))?)",
    re.MULTILINE,
)


def _build_compact_summary(ddl: str) -> Optional[str]:
    """
    Build a one-liner summary from a full DDL.
    E.g.: "paciente_asignacion (codigo_establecimiento varchar(16) PK, codigo_paciente varchar(20), ...)"
    """
    table_name = _extract_table_name_from_ddl(ddl)
    if not table_name:
        return None

    # Find PK columns
    pk_cols = set()
    pk_match = re.search(r"PRIMARY\s+KEY\s*\(([^)]+)\)", ddl, re.IGNORECASE)
    if pk_match:
        pk_cols = {c.strip().lower() for c in pk_match.group(1).split(",")}

    # Extract columns
    columns = []
    for match in _SIMPLE_COL_PATTERN.finditer(ddl):
        col_name = match.group(1).lower()
        col_type = match.group(2).strip()
        # Skip constraint lines
        if col_name.upper() in ("PRIMARY", "FOREIGN", "UNIQUE", "CHECK", "CONSTRAINT"):
            continue
        entry = f"{col_name} {col_type}"
        if col_name in pk_cols:
            entry += " PK"
        columns.append(entry)

    if not columns:
        return None

    if len(columns) > _MAX_SUMMARY_COLUMNS:
        columns = columns[:_MAX_SUMMARY_COLUMNS] + ["..."]

    return f"{table_name} ({', '.join(columns)})"


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class Text2SQLEngine:
    """
    RAG-based Text-to-SQL engine using ChromaDB for context retrieval
    and PostgreSQL for query execution.
    """

    def __init__(
        self,
        # PostgreSQL configuration
        pg_host: str = "localhost",
        pg_port: int = 5432,
        pg_dbname: str = "postgres",
        pg_user: str = "postgres",
        pg_password: str = "",
        # ChromaDB configuration
        chroma_path: str = "./chroma_data",
        # Query configuration
        max_context_items: int = 10,
        max_result_rows: int = 1000,
        max_full_ddl: int = 15,
        max_summary_ddl: int = 50,
    ):
        # PostgreSQL setup
        self.pg_config = {
            "host": pg_host,
            "port": pg_port,
            "dbname": pg_dbname,
            "user": pg_user,
            "password": pg_password,
        }

        # ChromaDB setup — use GPU when available for faster embedding
        self.chroma_client = chromadb.PersistentClient(path=chroma_path)
        self._embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL,
            device=_DEVICE,
        )
        logger.info(f"Embedding model '{EMBEDDING_MODEL}' loaded on device='{_DEVICE}'")
        self.col_ddl = self.chroma_client.get_or_create_collection(
            name="ddl",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embedding_fn,
        )
        self.col_docs = self.chroma_client.get_or_create_collection(
            name="documentation",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embedding_fn,
        )
        self.col_qa = self.chroma_client.get_or_create_collection(
            name="question_sql",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self._embedding_fn,
        )

        # Config
        self.max_context_items = max_context_items
        self.max_result_rows = max_result_rows
        self.max_full_ddl = max_full_ddl
        self.max_summary_ddl = max_summary_ddl

        # Table catalog: table_name -> {summary, ddl, doc_id}
        self._table_catalog: dict[str, str] = {}   # table_name -> compact summary
        self._table_ddls: dict[str, str] = {}       # table_name -> full DDL text
        self._rebuild_table_catalog()

        logger.info(
            f"Text2SQL engine initialized: "
            f"db={pg_dbname}@{pg_host}:{pg_port}, "
            f"chroma={chroma_path}, "
            f"catalog={len(self._table_catalog)} tables"
        )

    # ------------------------------------------------------------------
    # Table Catalog
    # ------------------------------------------------------------------

    def _rebuild_table_catalog(self) -> None:
        """
        Rebuild the in-memory table catalog from active DDL documents in ChromaDB.
        Maps table_name -> compact summary and table_name -> full DDL.
        Only includes entries with active sources (seed, auto, approved).
        """
        self._table_catalog.clear()
        self._table_ddls.clear()

        if self.col_ddl.count() == 0:
            return

        all_ddls = self.col_ddl.get(
            where={"source": {"$in": list(_ACTIVE_SOURCES)}},
            include=["documents"],
        )
        for doc in all_ddls["documents"]:
            table_name = _extract_table_name_from_ddl(doc)
            if not table_name:
                continue
            summary = _build_compact_summary(doc)
            if summary:
                self._table_catalog[table_name] = summary
                self._table_ddls[table_name] = doc

        logger.info(f"Table catalog rebuilt: {len(self._table_catalog)} tables indexed")

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    @staticmethod
    def _make_id(content: str) -> str:
        """Generate a deterministic ID from content to prevent duplicates."""
        return hashlib.md5(content.encode()).hexdigest()

    def _sync_source(self, col, source: str, new_entries: list[tuple[str, str, dict]]) -> dict:
        """
        Replace all entries in `col` whose metadata.source == source with new_entries.

        new_entries: list of (id, document, metadata) tuples.

        IDs are content-hashed (md5), so if the seed data hasn't changed the
        IDs are identical and we skip the expensive re-embed entirely.

        When IDs differ, only upsert the actually new/changed entries and
        delete stale ones — unchanged entries (same ID) are left untouched
        to avoid unnecessary re-embedding.
        """
        new_id_set = {e[0] for e in new_entries}

        existing = col.get(where={"source": {"$eq": source}}, include=[])
        existing_ids = set(existing.get("ids", []))

        # Fast path: nothing changed — skip entirely
        if new_id_set == existing_ids:
            return {"source": source, "upserted": 0, "deleted": 0, "skipped": True}

        # Only upsert entries whose ID is not already in ChromaDB
        added_ids = new_id_set - existing_ids
        if added_ids:
            to_upsert = [(id_, doc, meta) for id_, doc, meta in new_entries if id_ in added_ids]
            col.upsert(
                ids=[e[0] for e in to_upsert],
                documents=[e[1] for e in to_upsert],
                metadatas=[e[2] for e in to_upsert],
            )

        # Delete entries that are no longer in the new set
        to_delete = list(existing_ids - new_id_set)
        if to_delete:
            col.delete(ids=to_delete)

        return {
            "source": source,
            "added": len(added_ids),
            "deleted": len(to_delete),
            "unchanged": len(new_id_set & existing_ids),
        }

    def train_seed_batch(
        self,
        source: str,
        ddls: list[str],
        docs: list[str],
        qa_pairs: list[tuple[str, str]],
    ) -> dict:
        """
        Replace every entry tagged `source` across all three collections with
        the provided lists. Idempotent and safe to run on every startup.

        `source` must be one of _SEED_SOURCES (e.g. 'seed:ambulatoria'). Each
        seed domain syncs independently — a sweep of one domain never touches
        the other, nor entries tagged {auto, approved, user, feedback}.
        """
        if source not in _SEED_SOURCES:
            raise ValueError(
                f"train_seed_batch: source must be one of {sorted(_SEED_SOURCES)}, "
                f"got {source!r}"
            )
        logger.info(
            f"train_seed_batch[{source}]: syncing {len(ddls)} DDLs, "
            f"{len(docs)} docs, {len(qa_pairs)} Q&A pairs"
        )

        ddl_entries: list[tuple[str, str, dict]] = []
        for ddl in ddls:
            ddl_clean = ddl.strip()
            if not ddl_clean:
                continue
            doc_id = self._make_id(ddl_clean)
            ddl_entries.append((doc_id, ddl_clean, {"source": source}))
        ddl_result = self._sync_source(self.col_ddl, source, ddl_entries)

        doc_entries: list[tuple[str, str, dict]] = []
        for doc in docs:
            doc_clean = doc.strip()
            if not doc_clean:
                continue
            doc_id = self._make_id(doc_clean)
            doc_entries.append((doc_id, doc_clean, {"source": source}))
        doc_result = self._sync_source(self.col_docs, source, doc_entries)

        qa_entries: list[tuple[str, str, dict]] = []
        for question, sql in qa_pairs:
            q = question.strip()
            s = sql.strip()
            if not q or not s:
                continue
            content = f"Question: {q}\nSQL: {s}"
            doc_id = self._make_id(content)
            qa_entries.append(
                (doc_id, content, {"question": q, "sql": s, "source": source})
            )
        qa_result = self._sync_source(self.col_qa, source, qa_entries)

        self._rebuild_table_catalog()

        summary = {
            "source": source,
            "ddl": ddl_result,
            "documentation": doc_result,
            "question_sql": qa_result,
        }
        logger.info(f"train_seed_batch[{source}] complete: {summary}")
        return summary

    def train_ddl(self, ddl: str, source: str = "user") -> str:
        """Train on a DDL statement (CREATE TABLE, etc.)."""
        ddl = ddl.strip()
        doc_id = self._make_id(ddl)
        self.col_ddl.upsert(ids=[doc_id], documents=[ddl], metadatas=[{"source": source}])
        logger.info(f"Trained DDL ({source}): {ddl[:80]}...")
        self._rebuild_table_catalog()
        return doc_id

    def train_documentation(self, doc: str, source: str = "user") -> str:
        """Train on documentation (business rules, definitions, etc.)."""
        doc = doc.strip()
        doc_id = self._make_id(doc)
        self.col_docs.upsert(ids=[doc_id], documents=[doc], metadatas=[{"source": source}])
        logger.info(f"Trained documentation ({source}): {doc[:80]}...")
        return doc_id

    def train_question_sql(self, question: str, sql: str, source: str = "user") -> str:
        """Train on a question-SQL pair (few-shot example)."""
        content = f"Question: {question.strip()}\nSQL: {sql.strip()}"
        doc_id = self._make_id(content)
        self.col_qa.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[{"question": question.strip(), "sql": sql.strip(), "source": source}],
        )
        logger.info(f"Trained Q&A ({source}): {question[:60]}...")
        return doc_id

    def train_from_information_schema(self) -> int:
        """
        Auto-train by reading the database's information_schema.

        Sweeps all source='auto' DDL entries via _sync_source so upstream
        ALTER/DROP TABLEs are reflected on every run (no stale ghosts). Other
        sources (seed, approved, user, feedback) are untouched.

        Returns the number of DDL entries synced.
        """
        logger.info("Auto-train: querying information_schema for all tables")
        query = """
            SELECT table_schema, table_name, column_name, data_type,
                   is_nullable, column_default, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema', 'dbt_analytics')
            ORDER BY table_schema, table_name, ordinal_position
        """
        df = self.execute_sql(query)
        if df is None or df.empty:
            logger.warning("Auto-train: no columns found in information_schema")
            # Sweep stale auto entries even when the schema is empty
            self._sync_source(self.col_ddl, "auto", [])
            self._rebuild_table_catalog()
            return 0

        logger.info(f"Auto-train: found {len(df)} columns across tables")
        entries: list[tuple[str, str, dict]] = []
        for (schema, table), group in df.groupby(["table_schema", "table_name"]):
            columns = []
            for _, row in group.iterrows():
                col_def = f"    {row['column_name']} {row['data_type']}"
                if row.get("character_maximum_length"):
                    col_def += f"({int(row['character_maximum_length'])})"
                if row["is_nullable"] == "NO":
                    col_def += " NOT NULL"
                if row.get("column_default"):
                    col_def += f" DEFAULT {row['column_default']}"
                columns.append(col_def)

            ddl = f"CREATE TABLE {schema}.{table} (\n"
            ddl += ",\n".join(columns)
            ddl += "\n);"
            ddl_stripped = ddl.strip()
            doc_id = self._make_id(ddl_stripped)
            entries.append((doc_id, ddl_stripped, {"source": "auto"}))

        result = self._sync_source(self.col_ddl, "auto", entries)
        self._rebuild_table_catalog()
        logger.info(
            f"Auto-train complete: {len(entries)} tables in information_schema, "
            f"sync result={result}"
        )
        return len(entries)

    def get_training_data(self) -> list[TrainingEntry]:
        """Return all training data entries."""
        logger.info("Fetching all training data entries")
        entries = []

        for entry_type, col in [("ddl", self.col_ddl), ("documentation", self.col_docs), ("question_sql", self.col_qa)]:
            data = col.get(include=["documents", "metadatas"])
            for doc_id, doc, meta in zip(data["ids"], data["documents"], data["metadatas"] or [{}] * len(data["ids"])):
                source = (meta or {}).get("source", "unknown")
                entries.append(TrainingEntry(id=doc_id, entry_type=entry_type, content=doc, source=source))

        logger.info(f"Fetched {len(entries)} training entries")
        return entries

    def approve_training_data(self, entry_id: str) -> bool:
        """Approve a pending training entry (changes source to 'approved'). Returns True if found."""
        logger.info(f"Approving training entry: {entry_id}")
        for col_name, col in [("ddl", self.col_ddl), ("docs", self.col_docs), ("qa", self.col_qa)]:
            try:
                existing = col.get(ids=[entry_id], include=["documents", "metadatas"])
                if existing["ids"]:
                    meta = existing["metadatas"][0] or {}
                    meta["source"] = "approved"
                    col.update(ids=[entry_id], metadatas=[meta])
                    logger.info(f"Approved training entry {entry_id} in collection '{col_name}'")
                    if col_name == "ddl":
                        self._rebuild_table_catalog()
                    return True
            except Exception as e:
                logger.debug(f"Entry {entry_id} not in collection '{col_name}': {e}")
                continue
        logger.warning(f"Training entry {entry_id} not found in any collection")
        return False

    def remove_training_data(self, entry_id: str) -> bool:
        """Remove a training entry by ID. Returns True if found and removed."""
        logger.info(f"Attempting to remove training entry: {entry_id}")
        for col_name, col in [("ddl", self.col_ddl), ("docs", self.col_docs), ("qa", self.col_qa)]:
            try:
                existing = col.get(ids=[entry_id])
                if existing["ids"]:
                    col.delete(ids=[entry_id])
                    logger.info(f"Removed training entry {entry_id} from collection '{col_name}'")
                    if col_name == "ddl":
                        self._rebuild_table_catalog()
                    return True
            except Exception as e:
                logger.debug(f"Entry {entry_id} not in collection '{col_name}': {e}")
                continue
        logger.warning(f"Training entry {entry_id} not found in any collection")
        return False

    # ------------------------------------------------------------------
    # Context Retrieval (RAG)
    # ------------------------------------------------------------------

    # Spanish + SQL stopwords to skip during keyword extraction
    _KEYWORD_STOPWORDS = {
        # Spanish
        "cuantos", "cuantas", "cuanto", "cuanta", "cuales", "cual", "como",
        "donde", "cuando", "quien", "quienes", "porque", "para", "desde",
        "hasta", "entre", "sobre", "este", "esta", "estos", "estas", "esos",
        "esas", "aquel", "aquella", "todos", "todas", "cada", "otro", "otra",
        "otros", "otras", "mismo", "misma", "tiene", "tienen", "hacer",
        "hizo", "hicieron", "hubo", "fueron", "sido", "esta", "estan",
        "tiene", "tienen", "puede", "pueden", "debe", "deben", "solo",
        "tambien", "pero", "sino", "aunque", "porque", "pues", "luego",
        "entonces", "mientras", "antes", "despues", "aqui", "alla",
        "mucho", "muchos", "mucha", "muchas", "poco", "pocos", "poca",
        "pocas", "todo", "toda", "nada", "algo", "alguien", "nadie",
        "mayor", "menor", "mejor", "peor", "primer", "ultimo", "ultima",
        "mostrar", "listar", "dame", "dime", "quiero", "necesito",
        "favor", "gracias", "hola", "buenas",
        "que", "del", "los", "las", "por", "con", "una", "unos", "unas",
        "mas", "hay", "fue", "son", "ser", "mes", "anho", "dia", "hoy",
        "ayer", "semana",
        # SQL / generic
        "select", "from", "where", "join", "left", "right", "inner",
        "outer", "group", "order", "limit", "count", "having", "distinct",
        "null", "true", "false", "and", "not", "the", "table", "column",
    }

    @staticmethod
    def _extract_tables_from_sql(sql_text: str) -> set[str]:
        """
        Extract table names referenced after FROM and JOIN keywords in SQL.
        Handles optional schema prefix (e.g., public.paciente_asignacion).
        Returns a set of table names (without schema, lowercased).
        """
        pattern = re.compile(
            r"(?:FROM|JOIN)\s+(?:(\w+)\.)?(\w+)",
            re.IGNORECASE,
        )
        tables = set()
        for match in pattern.finditer(sql_text):
            table_name = match.group(2).lower()
            if table_name not in ("select", "where", "on", "and", "or", "as"):
                tables.add(table_name)
        return tables

    def _extract_keywords(self, question: str) -> list[str]:
        """
        Extract meaningful keywords from a natural language question.
        Returns lowercased words >= 4 chars that aren't stopwords.
        """
        words = re.findall(r"[a-záéíóúñü]+", question.lower())
        return [w for w in words if len(w) >= 4 and w not in self._KEYWORD_STOPWORDS]

    # Metadata filter for active-only queries (unscoped — all domains)
    _ACTIVE_FILTER = {"source": {"$in": list(_ACTIVE_SOURCES)}}

    # Valid domain values for scoped retrieval.
    # "ambos" means the question spans both domains — search everything.
    _SCOPED_DOMAINS = {"ambulatoria", "internacion"}

    def _build_source_filter(self, domain: str | None) -> dict:
        """
        Build a ChromaDB `where` filter, optionally scoped to one domain.

        domain values:
          "ambulatoria" -> seed:ambulatoria + seed:common + auto + approved
          "internacion" -> seed:internacion + seed:common + auto + approved
          "ambos" / None / anything else -> all active sources (no filtering)
        """
        if domain in self._SCOPED_DOMAINS:
            scoped = {f"seed:{domain}", "seed:common", "seed:dbt", "auto", "approved"}
            return {"source": {"$in": list(scoped)}}
        return self._ACTIVE_FILTER

    def _semantic_ddl_search(self, question: str, where: dict | None = None) -> list[str]:
        """P1: DDLs from ChromaDB semantic similarity search."""
        if self.col_ddl.count() == 0:
            return []
        where = where or self._ACTIVE_FILTER
        n = min(self.max_context_items, self.col_ddl.count())
        results = self.col_ddl.query(query_texts=[question], n_results=n, where=where)
        if results["documents"] and results["documents"][0]:
            return list(results["documents"][0])
        return []

    def _example_sql_ddl_lookup(self, question_sql_docs: list[str], seen: set[str]) -> list[str]:
        """P2: DDLs for tables referenced in example SQL queries."""
        ddls = []
        for qa_doc in question_sql_docs:
            sql_part = qa_doc.split("SQL:", 1)[-1] if "SQL:" in qa_doc else qa_doc
            for table_name in self._extract_tables_from_sql(sql_part):
                if table_name not in seen and table_name in self._table_ddls:
                    ddls.append(self._table_ddls[table_name])
                    seen.add(table_name)
        return ddls

    @staticmethod
    def _extract_related_tables_from_ddl(ddl: str) -> set[str]:
        """
        Extract table names referenced in '-- Se une a: TABLE' comments within a DDL.
        These are the tables that the given table JOINs to — following them ensures
        the LLM has the full DDL for every table it needs to construct JOINs.
        """
        # Matches: "-- Se une a: TABLE_NAME" or "-- Se une a: TABLE_NAME.column"
        # or "-- Se une a: TABLE_NAME via ..."
        pattern = re.compile(r"--\s*Se une a:\s*(\w+)", re.IGNORECASE)
        tables = set()
        for match in pattern.finditer(ddl):
            table = match.group(1).lower()
            # Skip column references that accidentally matched
            if table not in ("via", "el", "la", "los", "las", "de", "del", "con"):
                tables.add(table)
        return tables

    def _related_ddl_lookup(self, collected_ddls: list[str], seen: set[str]) -> list[str]:
        """
        P3: Follow '-- Se une a:' relationship comments in already-collected DDLs.
        Pulls in the full DDL for any referenced table not yet in the result set.
        Single hop only (does not recurse) to avoid pulling the entire schema.
        """
        ddls = []
        for ddl in collected_ddls:
            for table_name in self._extract_related_tables_from_ddl(ddl):
                if table_name not in seen and table_name in self._table_ddls:
                    ddls.append(self._table_ddls[table_name])
                    seen.add(table_name)
        return ddls

    def _keyword_ddl_search(self, question: str, seen: set[str], limit: int = 0, where: dict | None = None) -> list[str]:
        """P4: DDLs matched by keyword substring search on the question."""
        if self.col_ddl.count() == 0 or limit <= 0:
            return []
        ddls = []
        for keyword in self._extract_keywords(question):
            if len(ddls) >= limit:
                break
            docs = self._keyword_ddl_get(keyword, limit, where)
            for doc in docs:
                name = _extract_table_name_from_ddl(doc)
                if name and name not in seen:
                    ddls.append(doc)
                    seen.add(name)
                    if len(ddls) >= limit:
                        break
        return ddls

    def _keyword_ddl_get(self, keyword: str, limit: int, source_filter: dict | None = None) -> list[str]:
        """Run a single ChromaDB keyword lookup, returning matched documents."""
        where = source_filter or self._ACTIVE_FILTER
        try:
            results = self.col_ddl.get(
                where=where,
                where_document={"$contains": keyword},
                limit=limit,
            )
            return results["documents"] or []
        except Exception as e:
            logger.warning(f"Keyword DDL search failed for '{keyword}': {e}")
            return []

    @staticmethod
    def _take(source: list[str], dest: list[str], limit: int) -> int:
        """Append items from *source* to *dest* until *limit* is reached.
        Returns the number of items appended."""
        before = len(dest)
        for item in source:
            if len(dest) >= limit:
                break
            dest.append(item)
        return len(dest) - before

    def _collect_full_ddls(self, question: str, question_sql_docs: list[str], where: dict | None = None) -> list[str]:
        """
        Collect full DDL strings in priority order:
        P1. Semantic search results from ChromaDB
        P2. Tables referenced in example SQL queries
        P3. Tables referenced in '-- Se une a:' comments (relationship following)
        P4. Tables matched by keyword search on the question

        Returns deduplicated list, hard-limited to max_full_ddl.
        Higher-priority phases fill slots first; lower phases get whatever
        budget remains. `where` is a ChromaDB metadata filter for domain scoping.
        """
        seen_tables: set[str] = set()
        limit = self.max_full_ddl
        full_ddls: list[str] = []

        # P1: Semantic search (dedup inline — raw results aren't pre-filtered)
        p1 = []
        for ddl in self._semantic_ddl_search(question, where):
            name = _extract_table_name_from_ddl(ddl)
            if name and name not in seen_tables:
                p1.append(ddl)
                seen_tables.add(name)
        p1_n = self._take(p1, full_ddls, limit)

        # P2: Tables from example SQL
        p2_n = self._take(
            self._example_sql_ddl_lookup(question_sql_docs, seen_tables),
            full_ddls, limit,
        ) if len(full_ddls) < limit else 0

        # P3: Follow relationship comments in collected DDLs (single hop)
        p3_n = self._take(
            self._related_ddl_lookup(list(full_ddls), seen_tables),
            full_ddls, limit,
        ) if len(full_ddls) < limit else 0

        # P4: Keyword matches (pass remaining budget to the query itself)
        remaining = limit - len(full_ddls)
        p4_n = self._take(
            self._keyword_ddl_search(question, seen_tables, limit=remaining, where=where),
            full_ddls, limit,
        ) if remaining > 0 else 0

        logger.info(
            f"Full DDL collection: {p1_n} semantic + {p2_n} examples + "
            f"{p3_n} relationships + {p4_n} keyword = "
            f"{len(full_ddls)} total (limit={limit})"
        )

        # Apply intelligent column pruning (blacklist) to remove audit/sync noise and save tokens
        pruned_ddls = []
        for ddl in full_ddls:
            pruned_ddl = re.sub(
                r"^\s*(modificacion_fecha|modificacion_hora|modificacion_usuario|btimestamp)\b.*\n?", 
                "", 
                ddl, 
                flags=re.MULTILINE
            )
            pruned_ddls.append(pruned_ddl)

        return pruned_ddls

    def _build_ddl_summaries(self, full_ddl_tables: set[str]) -> list[str]:
        """
        Return compact one-liner summaries for all tables NOT in the full DDL set.
        Sorted alphabetically, capped at max_summary_ddl.
        """
        summaries = []
        for table_name in sorted(self._table_catalog):
            if table_name not in full_ddl_tables:
                summaries.append(self._table_catalog[table_name])
                if len(summaries) >= self.max_summary_ddl:
                    break
        return summaries

    def retrieve_context(self, question: str, domain: str | None = None) -> dict[str, list[str]]:
        """
        Retrieve relevant context from ChromaDB for a question.

        domain: optional domain hint from the caller (LLM classification).
          "ambulatoria" -> only ambulatoria + common context
          "internacion" -> only internacion + common context
          "ambos"       -> both domains (same as None)
          None          -> both domains (no filtering)

        Returns two tiers of DDL:
        - ddl: full CREATE TABLE statements for the most relevant tables
        - ddl_summary: compact one-liner summaries for all other known tables

        Plus documentation and example question-SQL pairs.
        Always-include docs are prepended to documentation. They are not
        stored in ChromaDB so there is no duplication risk with semantic results.
        """
        where = self._build_source_filter(domain)
        logger.info(f"retrieve_context: domain={domain!r}, source_filter={where}")

        # Start with always-include critical docs, then append semantic results
        documentation: list[str] = list(_ALWAYS_INCLUDE_DOCS)
        question_sql: list[str] = []

        for col, target_list in [
            (self.col_docs, documentation),
            (self.col_qa, question_sql),
        ]:
            if col.count() == 0:
                continue
            n = min(self.max_context_items, col.count())
            results = col.query(query_texts=[question], n_results=n, where=where)
            if results["documents"] and results["documents"][0]:
                target_list.extend(results["documents"][0])

        # Collect full DDLs with priority ordering
        full_ddls = self._collect_full_ddls(question, question_sql, where)

        # Build summaries for remaining tables
        full_ddl_tables = {_extract_table_name_from_ddl(d) for d in full_ddls} - {None}
        ddl_summaries = self._build_ddl_summaries(full_ddl_tables)

        logger.info(
            f"Context: domain={domain!r}, {len(full_ddls)} full DDL, {len(ddl_summaries)} summaries, "
            f"{len(documentation)} docs ({len(_ALWAYS_INCLUDE_DOCS)} always-include + "
            f"{len(documentation) - len(_ALWAYS_INCLUDE_DOCS)} semantic), "
            f"{len(question_sql)} Q&A pairs"
        )

        return {
            "ddl": full_ddls,
            "ddl_summary": ddl_summaries,
            "documentation": documentation,
            "question_sql": question_sql,
        }

    # ------------------------------------------------------------------
    # SQL Execution
    # ------------------------------------------------------------------

    def execute_sql(self, sql: str) -> Optional[pd.DataFrame]:
        """
        Execute a SQL query against PostgreSQL and return results as a DataFrame.
        Opens a fresh connection per query (simple, safe, no connection leaks).
        """
        conn = None
        try:
            # Set a 30-minute statement timeout to kill runaway queries (1800000 ms)
            conn = psycopg2.connect(**self.pg_config, options="-c statement_timeout=1800000")
            conn.set_session(readonly=True, autocommit=True)
            df = pd.read_sql_query(sql, conn)
            return df
        except psycopg2.Error as e:
            logger.error(f"PostgreSQL error: {e.pgerror or e}")
            raise
        finally:
            if conn:
                conn.close()

    def execute_validated(self, sql: str) -> SQLResult:
        """
        Validate and execute a SQL query. Returns a structured result.
        This is the main entry point for the /api/execute endpoint.
        """
        logger.info(f"execute_validated: sql={sql[:200]}")

        # Validate
        is_valid, validation_error = validate_sql(sql)
        if not is_valid:
            logger.warning(f"SQL validation failed: {validation_error}. SQL: {sql}")
            return SQLResult(
                sql=sql, results=None, row_count=0,
                error=validation_error, is_valid=False,
            )

        # Execute
        try:
            df = self.execute_sql(sql)
            if df is None:
                logger.warning("Query returned None")
                return SQLResult(
                    sql=sql, results=None, row_count=0,
                    error="Query returned no results", is_valid=True,
                )

            row_count = len(df)
            logger.info(f"Query returned {row_count} rows")
            if row_count > self.max_result_rows:
                logger.info(f"Truncating results from {row_count} to {self.max_result_rows}")
                df = df.head(self.max_result_rows)

            results = df.to_dict(orient="records")
            return SQLResult(
                sql=sql, results=results, row_count=row_count,
                error=None, is_valid=True,
            )

        except Exception as e:
            logger.error(f"Query execution failed: {type(e).__name__}: {e}", exc_info=True)
            return SQLResult(
                sql=sql, results=None, row_count=0,
                error=f"Query execution failed: {str(e)}", is_valid=True,
            )

    # ------------------------------------------------------------------
    # Health Check
    # ------------------------------------------------------------------

    def health_check(self) -> dict:
        """Check connectivity to PostgreSQL and ChromaDB."""
        logger.info("Running health check...")
        status = {"postgres": False, "chromadb": False}

        # ChromaDB
        try:
            count = self.col_ddl.count()
            status["chromadb"] = True
            logger.info(f"Health: ChromaDB OK (ddl collection has {count} entries)")
        except Exception as e:
            logger.error(f"Health: ChromaDB FAILED: {type(e).__name__}: {e}", exc_info=True)

        # PostgreSQL
        try:
            df = self.execute_sql("SELECT 1 AS ok")
            status["postgres"] = df is not None and not df.empty
            logger.info("Health: PostgreSQL OK")
        except Exception as e:
            logger.error(f"Health: PostgreSQL FAILED: {type(e).__name__}: {e}", exc_info=True)

        training_stats = {
            "ddl_count": self.col_ddl.count(),
            "documentation_count": self.col_docs.count(),
            "question_sql_count": self.col_qa.count(),
            "catalog_tables": len(self._table_catalog),
        }

        logger.info(f"Health check complete: status={status}, training={training_stats}")
        return {"status": status, "training": training_stats}
