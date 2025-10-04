
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Iterable

# ---------- Helper -------------------------------------------------------------
def _join(xs: Iterable[str]) -> str:
    xs = list(xs)
    if not xs:
        return ""
    return ", ".join(str(x) for x in xs)

# ---------- Templates ----------------------------------------------------------
@dataclass(frozen=True)
class PromptTemplates:
    planner: str
    implement: str
    review: str

    def render(self, kind: str, **kwargs: Any) -> str:
        if kind == "planner":
            return self.planner.format(**kwargs)
        if kind == "implement":
            return self.implement.format(**kwargs)
        if kind == "review":
            return self.review.format(**kwargs)
        raise KeyError(f"Unknown prompt kind: {kind!r}")

# German (DE) defaults — concise, step-focused
DEFAULT_DE = PromptTemplates(
    planner=(
        "Ziel: {goal}\n"
        "Erstelle einen kurzen, schrittweisen Plan, der die Deliverables erfüllt:\n{deliverables}\n"
        "Beachte die Constraints:\n{constraints}\n"
        "Gib nur den Plan aus."
    ),
    implement=(
        "Implementiere exakt basierend auf diesem Plan:\n{plan}\n\n"
        "Muss erfüllen: {deliverables}\n"
        "Constraints: {constraints}"
    ),
    review=(
        "Prüfe das Ergebnis strikt gegen Deliverables ({deliverables}) und Constraints ({constraints}).\n"
        "Gib ein kurzes Urteil (OK/Änderungen nötig) und liste konkrete Abweichungen auf."
    ),
)

def render_planner(goal: str, deliverables: Iterable[str], constraints: Iterable[str], templates: PromptTemplates = DEFAULT_DE) -> str:
    return templates.render(
        "planner",
        goal=goal,
        deliverables=_join(deliverables),
        constraints=_join(constraints),
    )

def render_implement(plan: str, deliverables: Iterable[str], constraints: Iterable[str], templates: PromptTemplates = DEFAULT_DE) -> str:
    return templates.render(
        "implement",
        plan=plan,
        deliverables=_join(deliverables),
        constraints=_join(constraints),
    )

def render_review(deliverables: Iterable[str], constraints: Iterable[str], templates: PromptTemplates = DEFAULT_DE) -> str:
    return templates.render(
        "review",
        deliverables=_join(deliverables),
        constraints=_join(constraints),
    )
