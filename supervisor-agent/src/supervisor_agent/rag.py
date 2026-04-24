"""RAG module — ChromaDB initialization and similarity search."""

import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from supervisor_agent.config import settings

logger = logging.getLogger(__name__)

# Default persist directory next to the project root
_DEFAULT_DB_DIR = str(Path(__file__).resolve().parents[3] / "chroma_db")
_COLLECTION_NAME = "latex_knowledge"


def _get_client(persist_dir: Optional[str] = None) -> chromadb.ClientAPI:
    path = persist_dir or _DEFAULT_DB_DIR
    return chromadb.PersistentClient(path=path)


def _get_embedding_fn() -> OpenAIEmbeddingFunction:
    kwargs: dict = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["api_base"] = settings.openai_base_url
    return OpenAIEmbeddingFunction(**kwargs)


def get_collection(persist_dir: Optional[str] = None):
    """Return (or create) the latex_knowledge collection."""
    client = _get_client(persist_dir)
    return client.get_or_create_collection(
        name=_COLLECTION_NAME,
        embedding_function=_get_embedding_fn(),
    )


def query_similar(query_text: str, n_results: int = 5, persist_dir: Optional[str] = None) -> list[str]:
    """Query ChromaDB for the top-K most similar LaTeX chunks.

    Returns a list of document strings. If the collection is empty or
    ChromaDB is unavailable, returns an empty list with a warning.
    """
    try:
        col = get_collection(persist_dir)
        if col.count() == 0:
            logger.warning("ChromaDB collection is empty — skipping retrieval.")
            return []
        results = col.query(query_texts=[query_text], n_results=min(n_results, col.count()))
        docs = results.get("documents", [[]])[0]
        logger.info(f"RAG retrieved {len(docs)} chunks for query: {query_text[:80]}...")
        return docs
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        return []
