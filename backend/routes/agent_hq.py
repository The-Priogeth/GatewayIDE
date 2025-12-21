# backend/routes/agent_hq.py
from __future__ import annotations

import hmac
import hashlib
import os
import re
import difflib
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/agent-hq", tags=["agent-hq"])

ENV_BEARER = "AGENTHQ_BEARER_TOKEN"
ENV_GH_SECRET = "GITHUB_WEBHOOK_SECRET"


def _get_env(name: str) -> str:
    return os.getenv(name, "").strip()


def _consteq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def _verify_bearer(request: Request) -> None:
    token = _get_env(ENV_BEARER)
    if not token:
        raise HTTPException(status_code=500, detail=f"Server misconfigured: {ENV_BEARER} missing")

    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    got = auth.split(" ", 1)[1].strip()

    if not _consteq(got, token):
        raise HTTPException(status_code=401, detail="Invalid Bearer token")


def _verify_github_signature(request: Request, raw_body: bytes) -> None:
    secret = _get_env(ENV_GH_SECRET)
    if not secret:
        raise HTTPException(status_code=500, detail=f"Server misconfigured: {ENV_GH_SECRET} missing")

    sig = request.headers.get("x-hub-signature-256", "").strip()
    if not sig:
        raise HTTPException(status_code=401, detail="Missing GitHub signature")

    mac = hmac.new(secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()

    if not _consteq(sig, expected):
        raise HTTPException(status_code=401, detail="Invalid GitHub signature")


async def verify_request(request: Request, raw_body: bytes) -> str:
    if request.headers.get("x-hub-signature-256"):
        _verify_github_signature(request, raw_body)
        return "github"
    _verify_bearer(request)
    return "bearer"


class DocsSyncRequest(BaseModel):
    repo: str = Field(..., description="e.g. The-Priogeth/GatewayIDE")
    ref: str = Field("main", description="branch or ref name")
    commit_sha: Optional[str] = Field(None, description="optional commit sha")
    changed_files: List[str] = Field(default_factory=list, description="paths changed")
    note: Optional[str] = Field(None, description="optional free-text context from AgentHQ")


class TodoItem(BaseModel):
    file: str
    title: str
    details: str
    priority: str = "P1"


class DocsSyncResponse(BaseModel):
    ok: bool = True
    auth_mode: str
    repo: str
    ref: str
    todos: List[TodoItem]
    patch_suggestion: Optional[str] = None


# -----------------------------
# Docs utilities (safe)
# -----------------------------
_PATH_TICK_RX = re.compile(r"`([^`]+)`")


def _find_repo_root(start: Path) -> Path:
    """
    Walk upwards until we find docs/root.md or hit filesystem root.
    Works in docker and local.
    """
    cur = start.resolve()
    for _ in range(12):  # enough for typical repo depth
        if (cur / "docs" / "root.md").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    raise FileNotFoundError("Could not locate repo root containing docs/root.md")


def _extract_code_paths(root_md: str) -> List[str]:
    """
    Extract backticked paths like `backend/agent_core/hma/hma.py`.
    Keep it conservative: only backticks.
    """
    paths = []
    for m in _PATH_TICK_RX.finditer(root_md):
        p = m.group(1).strip()
        # Only consider repo-like paths (avoid random inline code)
        if "/" in p and not p.startswith("http"):
            paths.append(p)
    return paths


def _build_patch_for_root_md(repo_root: Path) -> Optional[str]:
    """
    Generate a unified diff suggestion for docs/root.md:
    - Find referenced file paths in backticks
    - Detect which don't exist
    - Append a small 'Docs Sync' section listing stale references
    No auto-removals; safe + reviewable.
    """
    root_path = repo_root / "docs" / "root.md"
    old_text = root_path.read_text(encoding="utf-8")

    refs = _extract_code_paths(old_text)
    missing = []
    for r in sorted(set(refs)):
        # normalize: strip leading ./ if present
        rr = r[2:] if r.startswith("./") else r
        if not (repo_root / rr).exists():
            missing.append(r)

    if not missing:
        return None

    marker = "\n\n---\n\n## Docs Sync – stale references\n"
    if "## Docs Sync – stale references" in old_text:
        # already present, do not duplicate; only update content
        # Replace the section content between header and next header (simple heuristic)
        new_block = "## Docs Sync – stale references\n\n" + "\n".join(f"- [ ] `{p}` (missing)" for p in missing) + "\n"
        new_text = re.sub(
            r"## Docs Sync – stale references\s*\n(?:.*\n)*?(?=\n## |\Z)",
            new_block + "\n",
            old_text,
            flags=re.MULTILINE,
        )
    else:
        new_text = (
            old_text
            + marker
            + "\n".join(f"- [ ] `{p}` (missing)" for p in missing)
            + "\n"
        )

    diff = difflib.unified_diff(
        old_text.splitlines(True),
        new_text.splitlines(True),
        fromfile="docs/root.md",
        tofile="docs/root.md",
    )
    return "".join(diff)


@router.post("/docs-sync", response_model=DocsSyncResponse)
async def agenthq_docs_sync(request: Request) -> DocsSyncResponse:
    raw = await request.body()
    auth_mode = await verify_request(request, raw)

    try:
        payload = DocsSyncRequest.model_validate_json(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    rt = getattr(request.app.state, "runtime", None)
    if rt is None:
        raise HTTPException(status_code=500, detail="Runtime not initialized (app.state.runtime missing)")

    changed = set(payload.changed_files)

    def any_prefix(prefixes: list[str]) -> bool:
        return any(any(p.startswith(px) for p in changed) for px in prefixes)

    todos: List[TodoItem] = []
    if any_prefix(["backend/agent_core/"]):
        todos.append(
            TodoItem(
                file="docs/root.md",
                title="Sync agent_core documentation",
                details="agent_core changed. Spot-check root.md entries for HMA/messaging/adapters responsibilities and filenames.",
                priority="P1",
            )
        )
    if any_prefix(["backend/memory/"]):
        todos.append(
            TodoItem(
                file="docs/root.md",
                title="Sync memory subsystem documentation",
                details="memory subsystem changed. Spot-check root.md entries for MemoryManager/ZepMemory/GraphAPI and paths.",
                priority="P1",
            )
        )
    if any_prefix(["GatewayIDE.App/"]):
        todos.append(
            TodoItem(
                file="docs/root.md",
                title="Sync UI integration notes",
                details="UI changed. Verify root.md notes for UI ↔ backend contract, panels, endpoints.",
                priority="P2",
            )
        )
    if not todos and payload.changed_files:
        todos.append(
            TodoItem(
                file="docs/root.md",
                title="Spot-check root.md for touched areas",
                details="Files changed but no rule matched. Spot-check relevant root.md sections for touched modules.",
                priority="P2",
            )
        )

    # build patch suggestion for docs/root.md (safe: only appends / updates stale-ref list)
    try:
        repo_root = _find_repo_root(Path(__file__))
        patch = _build_patch_for_root_md(repo_root)
        if patch:
            todos.insert(
                0,
                TodoItem(
                    file="docs/root.md",
                    title="Fix stale references (auto-detected)",
                    details="Some backticked file references in root.md do not exist in the repo. Suggested patch adds a checklist section.",
                    priority="P1",
                ),
            )
    except Exception:
        patch = None

    return DocsSyncResponse(
        auth_mode=auth_mode,
        repo=payload.repo,
        ref=payload.ref,
        todos=todos,
        patch_suggestion=patch,
    )
