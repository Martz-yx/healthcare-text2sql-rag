import time
import re
import math
import logging
from typing import Optional, List, Set

logger = logging.getLogger("text2sql.cache")

# TTL in seconds: 10 minutes
CACHE_TTL = 600
SIMILARITY_THRESHOLD = 0.94

class CacheEntry:
    def __init__(
        self,
        raw_question: str,
        embedding: List[float],
        domain: str,
        rewritten_question: str,
        sql: str,
        formatted_answer: str,
    ):
        self.raw_question = raw_question
        self.normalized_question = self.normalize(rewritten_question)
        self.embedding = embedding
        self.domain = domain
        self.rewritten_question = rewritten_question
        self.sql = sql
        self.formatted_answer = formatted_answer
        self.timestamp = time.time()
        self.numbers = self.extract_numbers(rewritten_question)
        self.proper_nouns = self.extract_proper_nouns(rewritten_question)

    @staticmethod
    def normalize(text: str) -> str:
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        return " ".join(text.split())

    @staticmethod
    def extract_numbers(text: str) -> Set[str]:
        return set(re.findall(r'\b\d+\b', text))

    @staticmethod
    def extract_proper_nouns(text: str) -> Set[str]:
        # Extract capitalized words that are not the first word of the sentence
        words = text.split()
        proper = set()
        for i, word in enumerate(words):
            if i > 0 and word and word[0].isupper():
                clean = re.sub(r'[^\w]', '', word)
                if clean:
                    proper.add(clean.lower())
        return proper

    def is_expired(self) -> bool:
        return time.time() - self.timestamp > CACHE_TTL


_cache: List[CacheEntry] = []

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if v1 is None or v2 is None or len(v1) == 0 or len(v2) == 0:
        return 0.0
    dot_product = sum(x * y for x, y in zip(v1, v2))
    magnitude1 = math.sqrt(sum(x * x for x in v1))
    magnitude2 = math.sqrt(sum(x * x for x in v2))
    if not magnitude1 or not magnitude2:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)

def clean_expired_entries():
    global _cache
    _cache = [entry for entry in _cache if not entry.is_expired()]

def get_from_cache(rewritten_question: str, domain: Optional[str], embedding_fn) -> Optional[CacheEntry]:
    clean_expired_entries()
    
    normalized = CacheEntry.normalize(rewritten_question)
    incoming_numbers = CacheEntry.extract_numbers(rewritten_question)
    incoming_proper = CacheEntry.extract_proper_nouns(rewritten_question)
    
    # 1. Exact normalized match check (fast path)
    for entry in _cache:
        if (domain is None or entry.domain == domain) and entry.normalized_question == normalized:
            logger.info("Cache hit: exact normalized match for '%s'", rewritten_question)
            return entry

    # 2. Semantic match check
    if not embedding_fn:
        return None

    try:
        emb_result = embedding_fn([rewritten_question])
        if not emb_result:
            return None
        incoming_embedding = emb_result[0]
    except Exception as e:
        logger.error("Failed to generate embedding for cache lookup: %s", e)
        return None

    best_match: Optional[CacheEntry] = None
    best_sim = 0.0

    for entry in _cache:
        if domain is not None and entry.domain != domain:
            continue
        
        # Enforce exact match on numbers/digits
        if entry.numbers != incoming_numbers:
            continue
            
        # Enforce exact match on proper nouns (if any are present in either)
        if (entry.proper_nouns or incoming_proper) and entry.proper_nouns != incoming_proper:
            continue

        sim = cosine_similarity(incoming_embedding, entry.embedding)
        if sim > SIMILARITY_THRESHOLD and sim > best_sim:
            best_sim = sim
            best_match = entry

    if best_match:
        logger.info(
            "Cache hit: semantic match for '%s' (similar to '%s', sim=%.3f)",
            rewritten_question, best_match.rewritten_question, best_sim
        )
        return best_match

    return None

def add_to_cache(
    raw_question: str,
    domain: str,
    rewritten_question: str,
    sql: str,
    formatted_answer: str,
    embedding_fn
):
    clean_expired_entries()
    
    embedding = []
    if embedding_fn:
        try:
            emb_result = embedding_fn([rewritten_question])
            if emb_result:
                embedding = emb_result[0]
        except Exception as e:
            logger.error("Failed to generate embedding for caching: %s", e)

    entry = CacheEntry(
        raw_question=raw_question,
        embedding=embedding,
        domain=domain,
        rewritten_question=rewritten_question,
        sql=sql,
        formatted_answer=formatted_answer
    )
    _cache.append(entry)
    logger.info("Added query to cache: '%s'", raw_question)
