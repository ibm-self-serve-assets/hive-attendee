import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv


class BackendConfig(BaseModel):
    simulation_server_url: str = "http://localhost:8080"
    workshop_access_token: Optional[str] = None
    confluent_bootstrap_server: Optional[str] = None
    confluent_api_key: Optional[str] = None
    confluent_api_secret: Optional[str] = None

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

        sim_url = env_dict.get("SIMULATION_SERVER_URL", "http://localhost:8080").rstrip("/")
        token = env_dict.get("WORKSHOP_ACCESS_TOKEN")
        bootstrap = env_dict.get("CONFLUENT_BOOTSTRAP_SERVER")
        key = env_dict.get("CONFLUENT_API_KEY")
        secret = env_dict.get("CONFLUENT_API_SECRET")

        host = env_dict.get("LOCAL_BACKEND_HOST", "127.0.0.1")
        port = int(env_dict.get("LOCAL_BACKEND_PORT", 8001))
        fe_port = int(env_dict.get("LOCAL_FRONTEND_PORT", 5174))

        return cls(
            simulation_server_url=sim_url,
            workshop_access_token=token if token != "CHANGE_ME" else None,
            confluent_bootstrap_server=bootstrap if bootstrap != "CHANGE_ME" else None,
            confluent_api_key=key if key != "CHANGE_ME" else None,
            confluent_api_secret=secret if secret != "CHANGE_ME" else None,
            local_backend_host=host,
            local_backend_port=port,
            local_frontend_port=fe_port,
        )
