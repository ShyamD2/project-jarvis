"""
Knowledge Base & RAG Index for J.A.R.V.I.S.
Stores documents, system runbooks, and project data with fast semantic retrieval.
"""

from __future__ import annotations
import math
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class DocumentChunk:
    doc_id: str
    title: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class KnowledgeRAG:
    def __init__(self):
        self.documents: List[DocumentChunk] = []
        # Pre-populate with core JARVIS runbooks
        self.index_document(
            doc_id="rb_01",
            title="Emergency Stand-Down Runbook",
            content="When the user invokes Stand Down, freeze all agent execution, cancel active threads, and notify all interfaces.",
            metadata={"category": "safety"}
        )
        self.index_document(
            doc_id="rb_02",
            title="ESP32 IoT Protocol",
            content="ESP32 devices communicate via MQTT on topic jarvis/devices/{device_id}/command. Relays control lights, lamps, and power.",
            metadata={"category": "hardware"}
        )
        self.index_document(
            doc_id="rb_03",
            title="AWS Terraform Deployment Guide",
            content="Terraform configs reside in infrastructure/terraform. Stacks deploy via environment modules with S3 remote state.",
            metadata={"category": "cloud"}
        )

    def index_document(self, doc_id: str, title: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        chunk = DocumentChunk(doc_id=doc_id, title=title, content=content, metadata=metadata or {})
        self.documents.append(chunk)

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Keyword relevance search across indexed knowledge"""
        q_tokens = set(re.findall(r"\w+", query.lower()))
        scored_docs = []

        for doc in self.documents:
            doc_tokens = re.findall(r"\w+", (doc.title + " " + doc.content).lower())
            score = sum(1 for t in q_tokens if t in doc_tokens)
            if score > 0:
                scored_docs.append((score, doc))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, doc in scored_docs[:top_k]:
            results.append({
                "doc_id": doc.doc_id,
                "title": doc.title,
                "content": doc.content,
                "score": score,
                "metadata": doc.metadata
            })
        return results


knowledge_rag = KnowledgeRAG()
