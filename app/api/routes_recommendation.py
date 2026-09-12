from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/investors/{investor_id}/recommendations", tags=["recommendations"])


@router.post("/")
def generate_recommendation(investor_id: int):
    """Stub: wires up once the AI Recommendation Engine (build order step 4) lands."""
    raise HTTPException(status_code=501, detail="Recommendation Engine not implemented yet")
