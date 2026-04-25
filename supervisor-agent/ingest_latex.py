"""Offline script — clean, chunk and ingest LaTeX files into ChromaDB.

Enhanced: extracts section/subsection titles and binds them as metadata
to each chunk for precise RAG retrieval.
"""

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

# Regex to capture \section{...}, \subsection{...}, \subsubsection{...}
_SECTION_RE = re.compile(
    r"\\(section|subsection|subsubsection)\{([^}]*)\}"
)


def clean_latex(raw: str) -> str:
    """Strip preamble, postamble and single-line comments."""
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", raw, re.DOTALL)
    body = m.group(1) if m else raw
    body = re.sub(r"(?m)^%.*$", "", body)
    body = re.sub(r"(?<!\\)%.*", "", body)
    return body.strip()


def _find_section_for_chunk(full_text: str, chunk: str) -> dict:
    """Determine which section a chunk belongs to.

    Walks backwards from the chunk's position in *full_text* to find the
    nearest \\section / \\subsection heading.
    """
    pos = full_text.find(chunk[:80])  # match on first 80 chars
    if pos == -1:
        return {"section": "", "level": ""}

    preceding = full_text[:pos]
    matches = list(_SECTION_RE.finditer(preceding))
    if not matches:
        return {"section": "", "level": ""}

    last = matches[-1]
    return {"section": last.group(2).strip(), "level": last.group(1)}


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
            sec_info = _find_section_for_chunk(cleaned, chunk)
            all_docs.append(chunk)
            all_ids.append(f"tex_{idx}")
            all_metas.append({
                "source": fpath.name,
                "section": sec_info["section"],
                "level": sec_info["level"],
            })
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
    logger.info(
        f"Done — ingested {len(all_docs)} chunks. "
        f"Collection total: {collection.count()}"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingest_latex.py <path/to/tex/directory>")
        print("Example: python ingest_latex.py ./data/papers")
        sys.exit(1)
    ingest_directory(sys.argv[1])
