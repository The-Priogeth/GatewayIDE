"""
tools.py — einfache Tool-Registry für die Captains.
Captains können im Output Zeilen wie TOOL:add({"a":2,"b":3}) schreiben.
chat.py ruft dann call_tool(spec) auf, um die Funktion auszuführen.
"""

import datetime, math, json


def now_iso() -> str:
    """UTC-Zeitstempel im ISO-Format."""
    return datetime.datetime.utcnow().isoformat() + "Z"


def add(a: float, b: float) -> float:
    """Addition von zwei Zahlen."""
    return float(a) + float(b)


def sqrt(x: float) -> float:
    """Quadratwurzel."""
    return math.sqrt(float(x))


REGISTRY = {
    "now_iso": lambda: now_iso(),
    "add": lambda a, b: add(a, b),
    "sqrt": lambda x: sqrt(x),
}


def call_tool(spec: str) -> str:
    """
    Führt eine TOOL-Spezifikation wie 'TOOL:add({"a":2,"b":3})' aus
    und gibt ein JSON-Resultat zurück.
    """
    try:
        if not spec.startswith("TOOL:"):
            raise ValueError("spec muss mit TOOL: beginnen")

        call = spec[len("TOOL:") :].strip()
        if "(" not in call or not call.endswith(")"):
            raise ValueError("Syntax ungültig")

        name, argstr = call.split("(", 1)
        name = name.strip()
        argstr = argstr[:-1]  # schließe ')'

        args = {}
        if argstr:
            args = json.loads(argstr)
            if not isinstance(args, dict):
                raise ValueError("args_json muss ein Objekt sein")

        if name not in REGISTRY:
            raise KeyError(f"Unbekanntes Tool: {name}")

        fn = REGISTRY[name]
        result = fn(**args) if args else fn()
        return json.dumps(
            {"ok": True, "name": name, "args": args, "result": result},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"ok": False, "error": repr(e)}, ensure_ascii=False)
