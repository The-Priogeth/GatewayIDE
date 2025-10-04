# backend/managers/bibliothek.py
from __future__ import annotations
from typing import Any, Dict, List, Optional

from backend.services.bibliothek import BibliothekService

class BibliothekAgent:
    """
    V3-Agent 'doc':
    - Aktionen via ctx:
        ctx["doc_action"] ∈ {"recall","remember"}
        ctx["path"]       = "notes/v2.md"
        ctx["query"]      = "...", ctx["k"]=5        (für recall)
        ctx["text"]       = "...", ctx["role"]="user|assistant|system" (für remember)
    - Rückgabe immer {content, actions, signals}
    """
    role = "doc"

    def __init__(self, service: Optional[BibliothekService] = None, *, zep_client=None, user_id=None):
        if service is None:
            assert zep_client and user_id, "Entweder service ODER (zep_client,user_id) übergeben."
            service = BibliothekService(zep_client=zep_client, user_id=user_id)
        self.service = service

    async def propose(self, goal: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
        action = (ctx.get("doc_action") or "").lower()
        path   = ctx.get("path")
        if action == "recall" and path and ctx.get("query"):
            results = await self.service.recall(path=path, query=ctx["query"], k=int(ctx.get("k", 5)))
            # Formatiere ein knappes, menschenlesbares Snippet
            lines: List[str] = []
            for r in results:
                txt = (r.get("text") or "").strip()
                if txt:
                    lines.append(f"- {txt}")
            content = "Treffer:\n" + ("\n".join(lines) if lines else "(keine)")
            return {"content": content, "actions": [], "signals": {"op": "recall", "count": len(results)}}

        if action == "remember" and path and ctx.get("text"):
            ok = await self.service.remember(path=path, text=str(ctx["text"]), role=str(ctx.get("role","assistant")))
            return {"content": "Gespeichert." if ok else "Fehlgeschlagen.", "actions": [], "signals": {"op": "remember", "ok": ok}}

        # Passiver Modus: nichts tun, nur Hinweis (Manager wählt üblicherweise 'brain' als ersten Sprecher)
        return {"content": "", "actions": [], "signals": {"op": "noop"}}
