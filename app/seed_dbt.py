"""
Script to seed the text-to-SQL engine with dbt models documentation.
It parses manifest.json and catalog.json from dbt_project/target
and injects rich DDL statements into ChromaDB.
"""

import json
import logging
import os
try:
    from app.engine import Text2SQLEngine
except ImportError:
    from engine import Text2SQLEngine

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env file from the parent directory (his_ai)
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=env_path)

DBT_TARGET_DIR = os.path.join(os.path.dirname(__file__), "..", "dbt_project", "target")

def load_json(filename: str):
    path = os.path.join(DBT_TARGET_DIR, filename)
    if not os.path.exists(path):
        logger.warning(f"File not found: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_ddls_from_dbt() -> list[str]:
    manifest = load_json("manifest.json")
    catalog = load_json("catalog.json")

    if not manifest or not catalog:
        logger.error("dbt artifacts missing. Please run `dbt docs generate` first.")
        return []

    nodes = manifest.get("nodes", {})
    catalog_nodes = catalog.get("nodes", {})

    ddls = []

    for node_id, node in nodes.items():
        if node.get("resource_type") != "model":
            continue

        model_name = node.get("name")
        schema = node.get("schema", "dbt_analytics")
        description = node.get("description", "").strip()

        # Get column definitions from catalog (types) and manifest (descriptions)
        catalog_columns = catalog_nodes.get(node_id, {}).get("columns", {})
        manifest_columns = node.get("columns", {})

        col_defs = []
        # Fallback to manifest columns if catalog is empty, preserving order
        all_cols = list(manifest_columns.keys())
        for c in catalog_columns.keys():
            if c not in all_cols:
                all_cols.append(c)
                
        for col_name in all_cols:
            cat_col = catalog_columns.get(col_name, {})
            man_col = manifest_columns.get(col_name, {})

            data_type = cat_col.get("type") or man_col.get("data_type") or "UNKNOWN"
            col_desc = man_col.get("description", "").strip()

            line = f"    {col_name} {data_type}"
            if col_desc:
                # remove newlines from description
                col_desc = " ".join(col_desc.split())
                line += f" -- {col_desc}"
            col_defs.append(line)

        # Build DDL string
        ddl = f"CREATE TABLE {schema}.{model_name} (\n"
        ddl += ",\n".join(col_defs)
        ddl += "\n);"

        if description:
            # prepend table comment
            ddl = f"-- TABLE DESCRIPTION: {description}\n" + ddl

        ddls.append(ddl)

    return ddls

def seed_dbt_models():
    logger.info("Starting dbt seed process...")
    engine = Text2SQLEngine(
        pg_dbname=os.getenv("PG_DBNAME", "his"),
        pg_host=os.getenv("PG_HOST", "localhost"),
        pg_user=os.getenv("PG_USER", ""),
        pg_password=os.getenv("PG_PASSWORD", ""),
        chroma_path=os.getenv("CHROMA_PATH", "./chroma_data")
    )
    
    ddls = generate_ddls_from_dbt()
    if not ddls:
        logger.warning("No DDLs generated from dbt.")
        return
    
    logger.info(f"Generated {len(ddls)} DDL statements from dbt models.")
    
    # Use sync_source to ensure idempotent updates for 'seed:dbt'
    entries = []
    for ddl in ddls:
        doc_id = engine._make_id(ddl)
        entries.append((doc_id, ddl, {"source": "seed:dbt"}))
    
    result = engine._sync_source(engine.col_ddl, "seed:dbt", entries)
    engine._rebuild_table_catalog()
    
    logger.info(f"dbt models sync complete: {result}")

if __name__ == "__main__":
    seed_dbt_models()
