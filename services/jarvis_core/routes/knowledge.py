"""
Hierarchical Memory & Knowledge API Router for Project J.A.R.V.I.S.
Exposes semantic recall across all 7 cognitive tiers.
"""

import os
import sys
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/memory"))

from hierarchical_memory import hierarchical_memory

router = APIRouter(prefix="/api/v1/knowledge", tags=["Hierarchical Memory"])


class RememberRequest(BaseModel):
    category: str = Field(default="preference", description="preference, procedural, or episode")
    key: str
    value: Any


@router.get("/search")
async def search_memory(q: str):
    """Recalls context across Working, Conversation, Procedural, Preferences, and RAG tiers"""
    recall_data = hierarchical_memory.recall(q)
    return {
        "status": "success",
        "query": q,
        "results": recall_data
    }


@router.post("/remember")
async def remember_knowledge(req: RememberRequest):
    """Persists a fact, preference, or procedure into cognitive memory"""
    if req.category == "preference":
        hierarchical_memory.learn_preference(req.key, req.value)
    elif req.category == "procedural":
        steps = req.value if isinstance(req.value, list) else [str(req.value)]
        hierarchical_memory.remember_procedural(req.key, steps)
    elif req.category == "episode":
        hierarchical_memory.remember_episode(req.key, "recorded", req.value if isinstance(req.value, dict) else {"val": req.value})

    return {
        "status": "stored",
        "category": req.category,
        "key": req.key
    }
