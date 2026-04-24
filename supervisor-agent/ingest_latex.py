"""Offline script — clean, chunk and ingest LaTeX files into ChromaDB."""

import re
import sys
import logging
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Allow running as standalone script
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from supervisor_agent.rag import get_collection  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── LaTeX separators (structure-aware) ──
LATEX_SEPARATORS = [
    "\\section{",
    "\\subsection{",
    "\\subsubsection{",
    "\n\n",
    "\n",
    " ",
]


def clean_latex(raw: str) -> str:
    """Strip preamble, postamble and single-line comments."""
    # Keep only content between \begin{document} and \end{document}
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", raw, re.DOTALL)
    body = m.group(1) if m else raw
    # Remove single-line comments (lines starting with %)
    body = re.sub(r"(?m)^%.*$", "", body)
    # Remove inline comments (% not preceded by \)
    body = re.sub(r"(?<!\\)%.*", "", body)
    return body.strip()


def chunk_latex(text: str, chunk_size: int = 800, chunk_overlap: int = 150) -> list[str]:
    """Split cleaned LaTeX body into chunks using structure-aware separators."""
    splitter = RecursiveCharacterTextSplitter(
        separators=LATEX_SEPARATORS,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    return splitter.split_text(text)


def ingest_directory(tex_dir: str):
    """Scan directory for .tex files → clean → chunk → store in ChromaDB."""
    tex_path = Path(tex_dir)
    if not tex_path.is_dir():
        logger.error(f"Directory not found: {tex_dir}")
        sys.exit(1)

    tex_files = list(tex_path.rglob("*.tex"))
    if not tex_files:
        logger.error(f"No .tex files found in {tex_dir}")
        sys.exit(1)

    logger.info(f"Found {len(tex_files)} .tex file(s)")

    collection = get_collection()
    all_docs, all_ids, all_metas = [], [], []
    idx = collection.count()

    for fpath in tex_files:
        logger.info(f"Processing: {fpath.name}")
        raw = fpath.read_text(encoding="utf-8", errors="ignore")
        cleaned = clean_latex(raw)
        if not cleaned:
            logger.warning(f"  Skipped (empty after cleaning): {fpath.name}")
            continue
        chunks = chunk_latex(cleaned)
        logger.info(f"  → {len(chunks)} chunks")
        for chunk in chunks:
            all_docs.append(chunk)
            all_ids.append(f"tex_{idx}")
            all_metas.append({"source": fpath.name})
            idx += 1

    if not all_docs:
        logger.warning("No chunks produced — nothing to ingest.")
        return

    # ChromaDB batch limit ~5461
    BATCH = 5000
    for i in range(0, len(all_docs), BATCH):
        collection.add(
            documents=all_docs[i : i + BATCH],
            ids=all_ids[i : i + BATCH],
            metadatas=all_metas[i : i + BATCH],
        )
    logger.info(f"Done — ingested {len(all_docs)} chunks. Collection total: {collection.count()}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_latex.py <path/to/tex/directory>")
        print("Example: python ingest_latex.py ./data/papers")
        sys.exit(1)
    ingest_directory(sys.argv[1])


def ingest_directory(tex_dir: str):
    """Scan directory for .tex files → clean → chunk → store in ChromaDB."""
    tex_path = Path(tex_dir)
    if not tex_path.is_dir():
        logger.error(f"Directory not found: {tex_dir}")
        sys.exit(1)

    tex_files = list(tex_path.rglob("*.tex"))
    if not tex_files:
        logger.error(f"No .tex files found in {tex_dir}")
        sys.exit(1)

    logger.info(f"Found {len(tex_files)} .tex file(s)")

    collection = get_collection()
    all_docs, all_ids, all_metas = [], [], []
    idx = collection.count()

    for fpath in tex_files:
        raw = fpath.read_text(encoding="utf-8", errors="ignore")
        cleaned = clean_latex(raw)
        if not cleaned:
            logger.warning(f"  Skipped (empty): {fpath.name}")
            continue
        chunks = chunk_latex(cleaned)
        logger.info(f"  {fpath.name} → {len(chunks)} chunks")
        for chunk in chunks:
            all_docs.append(chunk)
            all_ids.append(f"tex_{idx}")
            all_metas.append({"source": fpath.name})
            idx += 1

    if not all_docs:
        logger.warning("No chunks produced.")
        return

    BATCH = 5000
    for i in range(0, len(all_docs), BATCH):
        collection.add(
            documents=all_docs[i : i + BATCH],
            ids=all_ids[i : i + BATCH],
            metadatas=all_metas[i : i + BATCH],
        )
    logger.info(f"Done. Ingested {len(all_docs)} chunks, collection total: {collection.count()}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_latex.py <path/to/tex/directory>")
        sys.exit(1)
    ingest_directory(sys.argv[1])
