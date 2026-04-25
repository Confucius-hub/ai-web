"""Endpoint for local ONNX intent classification (own model)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_intent_classifier
from app.core.errors import DependencyUnavailable
from app.schemas.schemas import ClassifyRequest, ClassifyResponse

router = APIRouter(prefix="/classify", tags=["ml"])


@router.post("", response_model=ClassifyResponse, summary="Classify intent via own ONNX model")
async def classify(
    payload: ClassifyRequest,
    classifier=Depends(get_intent_classifier),
) -> ClassifyResponse:
    """# Своя модель — TF-IDF + LogReg, экспортированный в ONNX."""
    if classifier is None:
        raise DependencyUnavailable(
            "Local ONNX classifier is not loaded. "
            "Run: `docker compose exec api python scripts/train_local_model.py`"
        )
    label, confidence, scores = classifier.predict(payload.text)
    return ClassifyResponse(label=label, confidence=confidence, all_scores=scores)
