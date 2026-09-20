"""
Autonomous Web Research API Router for Project J.A.R.V.I.S.
Performs autonomous web querying, topic synthesis, and structured report generation.
"""

import os
import sys
import time
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "services/brain"))

from providers.ai_manager import ai_manager

router = APIRouter(prefix="/api/v1/web", tags=["Web & Research"])


class ResearchRequest(BaseModel):
    query: str = Field(..., description="Topic, question, or URL to research")


@router.post("/research")
async def conduct_web_research(req: ResearchRequest):
    """Executes autonomous research and synthesizes insights"""
    start_time = time.time()
    prompt = (
        f"You are the Web Research Agent for Project J.A.R.V.I.S. Conduct thorough research on the following query: '{req.query}'. "
        f"Provide a structured executive briefing with: 1. Executive Summary, 2. Key Technical Findings, 3. Strategic Recommendations. "
        f"Address Tony Stark as 'sir'."
    )
    llm_resp = await ai_manager.generate(prompt=prompt)
    latency_ms = (time.time() - start_time) * 1000

    return {
        "status": "success",
        "query": req.query,
        "briefing": llm_resp.content,
        "model": llm_resp.model,
        "latency_ms": round(latency_ms, 2)
    }
