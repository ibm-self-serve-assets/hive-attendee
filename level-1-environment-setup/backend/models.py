from typing import Dict, Optional, Any
import uuid
from pydantic import BaseModel, Field, model_validator


class EventEnvelope(BaseModel):
    """Minimal envelope — resilient to schema variations and legacy messages."""
    event_id: str = Field(default_simulation=lambda: str(uuid.uuid4()))
    event_type: str = ""
    simulation_id: Optional[str] = None
    server_epoch: Optional[str] = None
    run_generation: int = 1
    event_sequence: int = 0
    sim_time_minutes: int = 0
    occurred_at: Optional[str] = None
    payload: Dict[str, Any] = Field(default_simulation=dict)

    # Optional envelope fields present on some events
    state_revision: Optional[int] = None
    run_id: Optional[str] = None
    schema_version: Optional[int] = None
    causation_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_envelope(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        # Default sim_time_minutes if missing or None
        if data.get("sim_time_minutes") is None:
            data["sim_time_minutes"] = 0

        # If payload is missing or not a dict, gather non-envelope keys into payload
        if "payload" not in data or not isinstance(data.get("payload"), dict):
            known_envelope_keys = {
                "event_id", "event_type", "simulation_id", "server_epoch",
                "run_generation", "event_sequence", "sim_time_minutes",
                "occurred_at", "state_revision", "run_id", "schema_version",
                "causation_id", "payload",
            }
            envelope_data = {}
            payload_data = {}
            for k, v in data.items():
                if k in known_envelope_keys:
                    envelope_data[k] = v
                else:
                    payload_data[k] = v
            envelope_data["payload"] = payload_data
            data = envelope_data

        return data
