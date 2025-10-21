# backend/agent_core/messaging_protocol.py
# dünner Wrapper, damit bestehende Imports funktionieren
from backend.agent_core.messaging import ProtocolLogger  # re-export
__all__ = ["ProtocolLogger"]