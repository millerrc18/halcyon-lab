"""Documentation API routes."""
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["docs"])

# Docs we serve, in display order
DOCS = [
    # Core documentation
    {"id": "agents", "path": "AGENTS.md", "title": "AGENTS.md — Governance"},
    {"id": "readme", "path": "README.md", "title": "README"},
    {"id": "architecture", "path": "docs/architecture.md", "title": "Architecture"},
    {"id": "training-guide", "path": "docs/training-guide.md", "title": "Training Guide"},
    {"id": "roadmap", "path": "docs/roadmap.md", "title": "Roadmap"},

    # Research — Training & Model
    {"id": "research-training-formats", "path": "docs/research/Optimal_Training_Formats_for_Fine-Tuning_Equity_Trade_Commentary_Models.md", "title": "Research: Training Formats"},
    {"id": "research-quality-rubric", "path": "docs/research/Gold-Standard_Rubric_for_Scoring_Equity_Trade_Commentary__Process-Driven_LLM_Evaluation_Framework.md", "title": "Research: Quality Rubric"},
    {"id": "research-self-blinding", "path": "docs/research/Prompt_Engineering_for_Outcome-Conditioned_Training_Data_Generation__Self-Blinding_Pipelines_and_Reverse_Reasoning_Distillation.md", "title": "Research: Self-Blinding Pipelines"},
    {"id": "research-model-degradation", "path": "docs/research/Preventing_Model_Degradation_in_Iterative_QLoRA_Retraining__Data_Accumulation__Golden_Ratio_Mixing__and_Champion-Challenger_Evaluation.md", "title": "Research: Model Degradation Prevention"},
    {"id": "research-training-gaps", "path": "docs/research/Training_Data_Strategies_That_Give_Small_Financial_LLMs_a_Real_Edge.md", "title": "Research: Training Data Gaps & Innovation"},
    {"id": "research-grpo", "path": "docs/research/GRPO_for_Financial_LLMs_on_Consumer_Hardware__Practical_Implementation_and_Reward_Design.md", "title": "Research: GRPO Implementation"},
    {"id": "research-qwen-selection", "path": "docs/research/Best_Local_LLM_for_Financial_Analysis_on_RTX_3060__Qwen_Model_Selection_and_Fine-Tuning_Guide.md", "title": "Research: Qwen Model Selection"},

    # Research — Strategy & Data
    {"id": "research-alt-data", "path": "docs/research/Alternative_Data_Signals_for_Large-Cap_Short-Horizon_Trading__A_Cost-Benefit_Analysis_for_the_Halcyon_Lab_Stack.md", "title": "Research: Alternative Data Signals"},
    {"id": "research-halcyon-framework", "path": "docs/research/The_Halcyon_Framework__Compute__Value__and_Moat_for_a_Solo_AI_Trading_System.md", "title": "Research: Halcyon Framework (Compute, Value, Moat)"},

    # Research — Business & Operations
    {"id": "research-fund-path", "path": "docs/research/From_Solo_AI_Trader_to_Fund_Manager__A_Complete_Operational_Roadmap.md", "title": "Research: Solo Trader → Fund Manager"},
    {"id": "research-scaling-plan", "path": "docs/research/Halcyon_Lab_Scaling_Plan_Through_2026.md", "title": "Research: Scaling Plan Through 2026"},
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
