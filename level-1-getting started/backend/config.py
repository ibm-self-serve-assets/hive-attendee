import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from dotenv import load_dotenv

DEFAULT_SIMULATION_SERVER_URL = "http://localhost:8080"


def is_placeholder(value: Optional[str]) -> bool:
    """True for values copied from a template and never filled in (CHANGE_ME, <token_id>, your-...)."""
    v = (value or "").strip()
    return (
        v == "CHANGE_ME"
        or (v.startswith("<") and v.endswith(">"))
        or v.lower().startswith(("your-", "provided-by"))
    )


class BackendConfig(BaseModel):
    simulation_server_url: str = DEFAULT_SIMULATION_SERVER_URL
    workshop_access_token: Optional[str] = None
    attendee_id: Optional[str] = None
    confluent_bootstrap_server: Optional[str] = None
    confluent_api_key: Optional[str] = None
    confluent_api_secret: Optional[str] = None

    # Names of settings that still hold a template value; used to tell "not filled in"
    # apart from "wrong" when reporting configuration problems to the attendee.
    placeholder_vars: List[str] = []
    # True when SIMULATION_SERVER_URL is not set and the localhost default is in use.
    simulation_server_url_is_default: bool = False

    local_backend_host: str = "127.0.0.1"
    local_backend_port: int = 8001
    local_frontend_port: int = 5174

    @classmethod
    def load_from_env(cls, env_path: Optional[str] = None) -> "BackendConfig":
        if env_path:
            load_dotenv(env_path, override=True)
        else:
            loaded = load_dotenv(override=False)
            if not loaded:
                # Try spec-shared/.env first (shared across all specs), then local .env
                _root = Path(__file__).resolve().parent.parent.parent
                shared = _root / "spec-shared" / ".env"
                local = Path(__file__).resolve().parent.parent / ".env"
                load_dotenv(shared if shared.exists() else local, override=False)

        env_dict = dict(os.environ)
        placeholder_vars: List[str] = []

        def value(name: str) -> Optional[str]:
            raw = (env_dict.get(name) or "").strip()
            if not raw:
                return None
            if is_placeholder(raw):
                placeholder_vars.append(name)
                return None
            return raw

        raw_url = (env_dict.get("SIMULATION_SERVER_URL") or "").strip()
        if is_placeholder(raw_url):
            placeholder_vars.append("SIMULATION_SERVER_URL")
        sim_url = (raw_url or DEFAULT_SIMULATION_SERVER_URL).rstrip("/")

        host = env_dict.get("LOCAL_BACKEND_HOST", "127.0.0.1")
        port = int(env_dict.get("LOCAL_BACKEND_PORT", 8001))
        fe_port = int(env_dict.get("LOCAL_FRONTEND_PORT", 5174))

        return cls(
            simulation_server_url=sim_url,
            simulation_server_url_is_default=not raw_url,
            workshop_access_token=value("WORKSHOP_ACCESS_TOKEN"),
            attendee_id=value("ATTENDEE_ID"),
            confluent_bootstrap_server=value("CONFLUENT_BOOTSTRAP_SERVER"),
            confluent_api_key=value("CONFLUENT_API_KEY"),
            confluent_api_secret=value("CONFLUENT_API_SECRET"),
            placeholder_vars=placeholder_vars,
            local_backend_host=host,
            local_backend_port=port,
            local_frontend_port=fe_port,
        )
