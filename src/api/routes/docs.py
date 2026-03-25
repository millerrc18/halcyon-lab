"""Documentation API routes."""
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["docs"])

# Docs we serve, in display order
DOCS = [
    {"id": "agents", "path": "AGENTS.md", "title": "AGENTS.md — Governance"},
    {"id": "readme", "path": "README.md", "title": "README"},
    {"id": "architecture", "path": "docs/architecture.md", "title": "Architecture"},
    {"id": "training-guide", "path": "docs/training-guide.md", "title": "Training guide"},
    {"id": "roadmap", "path": "docs/roadmap.md", "title": "Roadmap"},
]


def _find_project_root() -> Path:
    """Walk up from this file to find the repo root (has AGENTS.md)."""
    p = Path(__file__).resolve()
    for parent in [p] + list(p.parents):
        if (parent / "AGENTS.md").exists():
            return parent
    return Path.cwd()


@router.get("/docs")
def list_docs():
    root = _find_project_root()
    result = []
    for doc in DOCS:
        fp = root / doc["path"]
        result.append({
            "id": doc["id"],
            "title": doc["title"],
            "available": fp.exists(),
        })
    return result


@router.get("/docs/{doc_id}")
def get_doc(doc_id: str):
    root = _find_project_root()
    for doc in DOCS:
        if doc["id"] == doc_id:
            fp = root / doc["path"]
            if not fp.exists():
                raise HTTPException(404, f"Document not found: {doc['path']}")
            return {
                "id": doc["id"],
                "title": doc["title"],
                "content": fp.read_text(encoding="utf-8"),
            }
    raise HTTPException(404, f"Unknown document: {doc_id}")
