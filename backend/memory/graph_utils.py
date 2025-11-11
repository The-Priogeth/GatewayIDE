# backend/memory/graph_utils.py
from __future__ import annotations

from typing import Any, Dict, Optional, Union
from datetime import datetime

__all__ = ["build_edge_payload"]

DateLike = Union[str, datetime, None]


def _iso(dt: DateLike) -> Optional[str]:
    """
    Normalisiert Datums-/Zeitangaben:
    - datetime -> ISO 8601 (UTC/Z-nahe ohne TZ-Annahme)
    - str      -> unverändert (angenommen bereits ISO 8601-kompatibel)
    - None     -> None
    """
    if dt is None:
        return None
    if isinstance(dt, datetime):
        # Keinen harten TZ-Zwang – überlasse Interpretation dem Backend/Zep.
        return dt.isoformat()
    if isinstance(dt, str):
        return dt.strip() or None
    # Fallback (unerwarteter Typ) – lieber weglassen als falschen Typ senden
    return None


def build_edge_payload(
    head_uuid: str,
    relation: str,
    tail_uuid: str,
    *,
    fact: Optional[str] = None,
    attributes: Optional[Dict[str, Any]] = None,
    rating: Optional[float] = None,
    valid_at: DateLike = None,
    invalid_at: DateLike = None,
    expired_at: DateLike = None,
) -> Dict[str, Any]:
    """
    Erzeugt das standardisierte Edge-Payload für Zep-Graph-APIs.

    Pflicht:
        head_uuid  – Quellknoten-UUID (source_node_uuid)
        relation   – Kantenbezeichnung (name/predicate)
        tail_uuid  – Zielknoten-UUID (target_node_uuid)

    Optional:
        fact       – Freitext/Begründung/Statement zur Kante
        attributes – Beliebige zusätzliche Eigenschaften (JSON-Objekt)
        rating     – Gewichtung/Score (float)
        valid_at   – ISO8601 oder datetime (Beginn Gültigkeit)
        invalid_at – ISO8601 oder datetime (Ende Gültigkeit)
        expired_at – ISO8601 oder datetime (Ablaufzeitpunkt)

    Rückgabe:
        Dict, direkt an die Graph-API übergebbar.
    """
    if not isinstance(head_uuid, str) or not head_uuid.strip():
        raise ValueError("head_uuid muss eine nicht-leere Zeichenkette sein.")
    if not isinstance(tail_uuid, str) or not tail_uuid.strip():
        raise ValueError("tail_uuid muss eine nicht-leere Zeichenkette sein.")
    if not isinstance(relation, str) or not relation.strip():
        raise ValueError("relation muss eine nicht-leere Zeichenkette sein.")

    payload: Dict[str, Any] = {
        "source_node_uuid": head_uuid.strip(),
        "target_node_uuid": tail_uuid.strip(),
        "name": relation.strip(),
    }

    if fact is not None:
        f = fact.strip()
        if f:
            payload["fact"] = f

    if attributes:
        # Nur dicts zulassen; leere dicts vermeiden
        if not isinstance(attributes, dict):
            raise ValueError("attributes muss ein Dictionary sein.")
        if attributes:
            payload["attributes"] = attributes

    if rating is not None:
        # Float-konvertierbar halten, aber nichts erzwingen
        payload["rating"] = float(rating)

    # Zeitfelder normalisieren
    v = _iso(valid_at)
    i = _iso(invalid_at)
    e = _iso(expired_at)
    if v is not None:
        payload["valid_at"] = v
    if i is not None:
        payload["invalid_at"] = i
    if e is not None:
        payload["expired_at"] = e

    return payload
