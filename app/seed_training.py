#!/usr/bin/env python3
"""
Training Seed Orchestrator

Shared infrastructure for the curated seed training set. The actual DDLs,
docs, and question-SQL examples live in per-domain modules:

    seed_ambulatoria.py  -> source='seed:ambulatoria' (outpatient / consulta)
    seed_internacion.py  -> source='seed:internacion' (inpatient / hospitalization)

Each module exposes populate() and uses the shared train_ddl / train_doc /
train_example dispatch defined below. The two domains sync independently —
rebuilding one never sweeps the other's entries.

Two ways to apply the seed:

1. CLI / HTTP (against a running service):
       python app/seed_training.py
   Each train_* call dispatches through HTTPSink against BASE_URL, one
   domain at a time, each POSTing with its own source tag.

2. In-process (called from main.py on startup):
       from seed_training import SEED_DOMAINS, collect_for
       for domain in SEED_DOMAINS:
           sink = collect_for(domain)
           engine.train_seed_batch(f"seed:{domain}", sink.ddls, sink.docs, sink.qa)
   collect_for() temporarily swaps the module-level sink for a CollectorSink,
   runs the domain's populate(), and returns the gathered lists for batch
   sync via train_seed_batch (which atomically replaces every entry tagged
   with the given source — adds new, deletes obsolete).
"""

import sys

BASE_URL = "http://localhost:80"


# ---------------------------------------------------------------------------
# Sink abstraction — train_* calls dispatch through the active _SINK.
# ---------------------------------------------------------------------------


class _Sink:
    """Receives training entries; subclasses decide how to dispatch."""

    def ddl(self, ddl: str) -> None:
        raise NotImplementedError

    def doc(self, doc: str) -> None:
        raise NotImplementedError

    def example(self, question: str, sql: str) -> None:
        raise NotImplementedError


class HTTPSink(_Sink):
    """Pushes each entry to the running text2sql service via HTTP. CLI mode."""

    def __init__(self, base_url: str = BASE_URL, source: str = "seed:ambulatoria"):
        # Lazy-import requests so importing this module in-process (from main.py)
        # doesn't require `requests` to be installed in the service container.
        import requests

        self._requests = requests
        self.base_url = base_url
        self.source = source

    def ddl(self, ddl: str) -> None:
        r = self._requests.post(
            f"{self.base_url}/api/train/ddl",
            json={"ddl": ddl, "source": self.source},
        )
        r.raise_for_status()
        print(f"  DDL trained: {ddl[:60]}...")

    def doc(self, doc: str) -> None:
        r = self._requests.post(
            f"{self.base_url}/api/train/documentation",
            json={"documentation": doc, "source": self.source},
        )
        r.raise_for_status()
        print(f"  Doc trained: {doc[:60]}...")

    def example(self, question: str, sql: str) -> None:
        r = self._requests.post(
            f"{self.base_url}/api/train/question-sql",
            json={"question": question, "sql": sql, "source": self.source},
        )
        r.raise_for_status()
        print(f"  Example trained: {question[:60]}...")


class CollectorSink(_Sink):
    """Collects entries into in-memory lists for engine.train_seed_batch."""

    def __init__(self) -> None:
        self.ddls: list[str] = []
        self.docs: list[str] = []
        self.qa: list[tuple[str, str]] = []

    def ddl(self, ddl: str) -> None:
        self.ddls.append(ddl)

    def doc(self, doc: str) -> None:
        self.docs.append(doc)

    def example(self, question: str, sql: str) -> None:
        self.qa.append((question, sql))


# Module-level sink. Set by the CLI (HTTPSink) or by collect_for
# (CollectorSink). Starts as None so accidental train_* calls fail loudly
# with a clear message instead of silently dropping data.
_SINK: "_Sink | None" = None


def _set_sink(sink: "_Sink | None") -> None:
    global _SINK
    _SINK = sink


def _require_sink() -> _Sink:
    if _SINK is None:
        raise RuntimeError(
            "seed_training: no sink configured. "
            "Run via `python app/seed_training.py` or use collect_for(domain)."
        )
    return _SINK


def train_ddl(ddl: str) -> None:
    """Dispatch a DDL entry to the active sink."""
    _require_sink().ddl(ddl)


def train_doc(doc: str) -> None:
    """Dispatch a documentation entry to the active sink."""
    _require_sink().doc(doc)


def train_example(question: str, sql: str) -> None:
    """Dispatch a question-SQL example to the active sink."""
    _require_sink().example(question, sql)


# ---------------------------------------------------------------------------
# Helpers used only by CLI mode
# ---------------------------------------------------------------------------


def auto_train():
    """Auto-discover schema from information_schema (HTTP)."""
    import requests

    print("Auto-discovering schema from database...")
    r = requests.post(f"{BASE_URL}/api/train/auto")
    r.raise_for_status()
    data = r.json()
    print(f"  Discovered {data['tables_discovered']} tables")


def check_health():
    """Verify the service is running (HTTP)."""
    import requests

    r = requests.get(f"{BASE_URL}/health")
    r.raise_for_status()
    health = r.json()
    print(f"Service health: {health['status']}")
    print(f"Training stats: {health['training']}")
    return all(health["status"].values())


# ---------------------------------------------------------------------------
# Seed domain orchestration
# ---------------------------------------------------------------------------


# Each entry is the suffix of a seed_<domain>.py module that exposes populate().
# The source tag used in ChromaDB is f"seed:{domain}" — kept in lockstep with
# _SEED_SOURCES in engine.py.
SEED_DOMAINS: tuple[str, ...] = ("common", "ambulatoria", "internacion")


def _load_domain(domain: str):
    """Import seed_<domain>.py lazily so a missing module fails loudly at call time."""
    import importlib

    return importlib.import_module(f"seed_{domain}")


def collect_for(domain: str) -> CollectorSink:
    """
    Run populate() for one seed domain against a fresh CollectorSink and return it.

    Used by main.py's startup hook to feed engine.train_seed_batch directly,
    without going through HTTP. Resets _SINK on exit so accidental later
    train_* calls fail loudly instead of silently appending.
    """
    module = _load_domain(domain)
    saved = _SINK
    sink = CollectorSink()
    _set_sink(sink)
    try:
        module.populate()
        return sink
    finally:
        _set_sink(saved)


def main():
    """CLI: push each seed domain via HTTP to a running text2sql service."""
    print("=" * 60)
    print("Text-to-SQL Training Seed Script")
    print("=" * 60)
    print()

    # Check service is running
    print("Checking service health...")
    try:
        if not check_health():
            print("WARNING: Some services are not healthy. Training may fail.")
    except Exception as e:
        print(f"ERROR: Cannot connect to {BASE_URL}: {e}")
        print("Make sure the text2sql service is running.")
        sys.exit(1)
    print()

    # Step 1: Auto-discover schema (optional, may fail on large databases)
    print("Step 1: Auto-discovering schema...")
    try:
        auto_train()
    except Exception as e:
        print(f"  Auto-train failed (non-critical, manual DDL will be added next): {e}")
    print()

    # Steps 2+: per-domain seed data via HTTPSink
    for domain in SEED_DOMAINS:
        source = f"seed:{domain}"
        print(f"--- Seeding domain: {domain} (source={source}) ---")
        _set_sink(HTTPSink(BASE_URL, source=source))
        try:
            _load_domain(domain).populate()
        except ModuleNotFoundError:
            print(f"  seed_{domain}.py not found; skipping")
        print()

    # Verify training data
    print("Final training stats:")
    check_health()
    print()
    print("Done! You can now test with:")
    print(f'  curl -X POST {BASE_URL}/api/context -H "Content-Type: application/json" \\')
    print('    -d \'{"question": "cuantas consultas hubo hoy?"}\'')


if __name__ == "__main__":
    # CLI mode. HTTPSink's source tag is overridden per-domain inside main().
    _set_sink(HTTPSink(BASE_URL))
    main()
