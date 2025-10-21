# backend/agent_core/pbuffer.py
# dünner Wrapper, damit bestehende Imports funktionieren
from backend.agent_core.messaging import PBuffer  # re-export
__all__ = ["PBuffer"]