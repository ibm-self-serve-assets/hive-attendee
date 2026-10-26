"""
Plain-language connection diagnostics for the attendee dashboard.

Every problem found while connecting (bad .env values, a simulation server that
cannot be reached or rejects the credentials, a Confluent cluster that cannot be
reached or signed in to) becomes an ``Issue``: a stable code, a short title
and what went wrong. Issues are logged to the backend console in
a readable block and sent to the dashboard in the state snapshot, so the
attendee sees the same explanation in both places.

Issues never include secrets: the access token, API key and API secret are
mentioned by variable name only.
"""

import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import httpx

from backend.config import BackendConfig, is_placeholder

SOURCE_CONFIG = "config"
SOURCE_SIM_SERVER = "simulation_server"
SOURCE_CONFLUENT = "confluent"

# librdkafka logs every failed connection attempt (~every 50ms). The pre-flight check
# reports its own failure as an Issue, so its client gets a logger that discards them.
_silent_kafka_logger = logging.getLogger("hive.kafka.preflight")
_silent_kafka_logger.addHandler(logging.NullHandler())
_silent_kafka_logger.propagate = False

_MAX_DETAIL = 300
_HOST_PORT_RE = re.compile(r"^[A-Za-z0-9._-]+:\d{1,5}$")

_AUTH_ERRORS = {"_AUTHENTICATION", "SASL_AUTHENTICATION_FAILED"}
_DNS_ERRORS = {"_RESOLVE"}
_TLS_ERRORS = {"_SSL"}


@dataclass
class Issue:
    code: str
    source: str
    title: str
    message: str = ""
    detail: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _trim(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    text = " ".join(str(text).split())
    return text if len(text) <= _MAX_DETAIL else text[: _MAX_DETAIL - 1] + "…"


def format_for_console(issue: Issue) -> str:
    """Multi-line block for the backend console / log file."""
    lines = [f"CONNECTION PROBLEM [{issue.code}]: {issue.title}"]
    if issue.message:
        lines.append(f"    What happened: {issue.message}")
    if issue.detail:
        lines.append(f"    Detail:        {issue.detail}")
    return "\n".join(lines)


# ── 1. Configuration (.env) ───────────────────────────────────────────────────

def validate_config(config: BackendConfig) -> List[Issue]:
    """Problems with the values in spec-shared/.env, found before any network call."""
    issues: List[Issue] = []

    # SIMULATION_SERVER_URL
    url = config.simulation_server_url
    if "SIMULATION_SERVER_URL" in config.placeholder_vars:
        issues.append(Issue(
            code="sim_url_not_set",
            source=SOURCE_CONFIG,
            title="SIMULATION_SERVER_URL has not been filled in",
            message="SIMULATION_SERVER_URL still contains the template text instead of a web address.",
        ))
    elif not _is_valid_http_url(url):
        issues.append(Issue(
            code="sim_url_invalid",
            source=SOURCE_CONFIG,
            title="SIMULATION_SERVER_URL is not a valid web address",
            message=f"SIMULATION_SERVER_URL is '{url}'. It must start with http:// or https:// and include a host name.",
        ))

    # WORKSHOP_ACCESS_TOKEN
    if not config.workshop_access_token:
        issues.append(Issue(
            code="token_missing",
            source=SOURCE_CONFIG,
            title="WORKSHOP_ACCESS_TOKEN has not been filled in",
            message="The dashboard has no workshop access token, so the simulation server cannot identify you.",
        ))

    # CONFLUENT_BOOTSTRAP_SERVER
    bootstrap = config.confluent_bootstrap_server
    if not bootstrap:
        issues.append(Issue(
            code="confluent_bootstrap_missing",
            source=SOURCE_CONFIG,
            title="CONFLUENT_BOOTSTRAP_SERVER has not been filled in",
            message="The dashboard does not know the address of your Confluent Cloud cluster.",
        ))
    else:
        problem = _bootstrap_format_problem(bootstrap)
        if problem:
            issues.append(Issue(
                code="confluent_bootstrap_invalid",
                source=SOURCE_CONFIG,
                title="CONFLUENT_BOOTSTRAP_SERVER is not in the expected format",
                message=f"CONFLUENT_BOOTSTRAP_SERVER is '{bootstrap}'. {problem}",
            ))

    # CONFLUENT_API_KEY / CONFLUENT_API_SECRET
    missing_creds = [
        name for name, val in (
            ("CONFLUENT_API_KEY", config.confluent_api_key),
            ("CONFLUENT_API_SECRET", config.confluent_api_secret),
        ) if not val
    ]
    if missing_creds:
        issues.append(Issue(
            code="confluent_credentials_missing",
            source=SOURCE_CONFIG,
            title="Confluent API key is incomplete",
            message=f"{' and '.join(missing_creds)} {'has' if len(missing_creds) == 1 else 'have'} not been filled in.",
        ))

    return issues


def _is_valid_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


def _bootstrap_format_problem(bootstrap: str) -> Optional[str]:
    if "://" in bootstrap:
        return "Remove the 'https://' or similar prefix; it should be just host:port."
    for entry in bootstrap.split(","):
        entry = entry.strip()
        if ":" not in entry:
            return "It is missing the port. Confluent Cloud uses port 9092, so it should end in :9092."
        if not _HOST_PORT_RE.match(entry):
            return "It should be a host name followed by a port, with no spaces or extra characters."
    return None


# ── 2. Simulation server ──────────────────────────────────────────────────────

def _server_error_fields(body: Any) -> "tuple[Optional[str], Optional[str]]":
    """Pull (error_code, message) out of the simulation server's error body.

    The server wraps errors as {"detail": {"error_code", "message"}} (FastAPI HTTPException)
    or returns {"error_code", "message"} directly (JSONResponse). A plain-text body is
    returned as the message. Anything else yields (None, None).
    """
    if isinstance(body, str):
        return None, body
    if isinstance(body, dict):
        inner = body.get("detail", body)
        if isinstance(inner, dict):
            return inner.get("error_code"), inner.get("message")
        if isinstance(inner, str):
            return None, inner
    return None, None


def classify_http_error(config: BackendConfig, status_code: int, body: Any) -> Issue:
    """
    Report an error response from the simulation server.

    The server's own message is shown as it is, so its wording is maintained in one
    place (the server). This only chooses a stable code.
    """
    code, message = _server_error_fields(body)
    structured = isinstance(body, dict)  # a JSON error from our server, not an HTML page or plain text
    server_message = _trim(message) if structured else None

    if status_code == 401 and "not enrolled" in (message or "").lower():
        issue_code = "attendee_not_enrolled"
    elif status_code == 401:
        issue_code = "token_rejected"
    elif status_code == 403 and code == "attendee_token_mismatch":
        issue_code = "attendee_id_mismatch"
    elif status_code in (404, 405):
        issue_code = "sim_url_wrong_service"
    elif status_code in (502, 503, 504):
        issue_code = "sim_server_unavailable"
    else:
        issue_code = "sim_server_error"

    return Issue(
        code=issue_code,
        source=SOURCE_SIM_SERVER,
        title=server_message or f"The simulation server at {config.simulation_server_url} answered with HTTP {status_code}",
        detail=None if structured else _trim(message),
    )


def classify_network_error(config: BackendConfig, exc: BaseException) -> Issue:
    """Explain a failure to talk to the simulation server at all."""
    url = config.simulation_server_url
    text = str(exc).lower()
    default_hint = (
        " SIMULATION_SERVER_URL is not set, so the dashboard tried this default address."
        if config.simulation_server_url_is_default else ""
    )
    detail = _trim(f"{type(exc).__name__}: {exc}")

    if isinstance(exc, (httpx.UnsupportedProtocol, httpx.InvalidURL)):
        return Issue(
            code="sim_url_invalid",
            source=SOURCE_CONFIG,
            title="SIMULATION_SERVER_URL is not a valid web address",
            message=f"SIMULATION_SERVER_URL is '{url}', which cannot be used. It must start with http:// or https://.",
            detail=detail,
        )

    if isinstance(exc, httpx.TimeoutException):
        return Issue(
            code="sim_timeout",
            source=SOURCE_SIM_SERVER,
            title="The simulation server did not respond in time",
            message=f"Waited for {url} but got no answer. The server may be starting up, busy, or blocked by your network.",
            detail=detail,
        )

    if isinstance(exc, httpx.ConnectError):
        if any(s in text for s in ("nodename nor servname", "name or service not known",
                                   "getaddrinfo", "name resolution", "no address associated")):
            return Issue(
                code="sim_host_not_found",
                source=SOURCE_SIM_SERVER,
                title="The simulation server address was not found",
                message=f"No server exists at {url}; the host name could not be found.{default_hint}",
                detail=detail,
            )
        if "ssl" in text or "certificate" in text:
            return Issue(
                code="sim_tls_failed",
                source=SOURCE_SIM_SERVER,
                title="Secure connection to the simulation server failed",
                message=f"The dashboard could not set up a secure (HTTPS) connection to {url}.",
                detail=detail,
            )
        return Issue(
            code="sim_unreachable",
            source=SOURCE_SIM_SERVER,
            title="Could not connect to the simulation server",
            message=f"Nothing is accepting connections at {url}.{default_hint}",
            detail=detail,
        )

    return Issue(
        code="sim_connection_failed",
        source=SOURCE_SIM_SERVER,
        title="Connecting to the simulation server failed",
        message=f"An unexpected problem occurred while contacting {url}.",
        detail=detail,
    )


def not_a_simulation_server(config: BackendConfig) -> Issue:
    """The URL answered successfully, but not with the Hive server's response."""
    return Issue(
        code="sim_url_wrong_service",
        source=SOURCE_SIM_SERVER,
        title="SIMULATION_SERVER_URL does not look like the simulation server",
        message=f"{config.simulation_server_url} answered, but its reply was not what a Hive simulation server sends.",
    )


def provisioning_timeout(config: BackendConfig, waited_seconds: int) -> Issue:
    return Issue(
        code="provisioning_timeout",
        source=SOURCE_SIM_SERVER,
        title="Your simulation is taking too long to set up",
        message=(
            f"The simulation server is still checking your Confluent cluster after {waited_seconds} seconds."
        ),
    )


def from_server_diagnostic(diagnostic: Optional[Dict[str, Any]], fallback_detail: Optional[str] = None) -> Issue:
    """Turn the simulation server's provisioning_error into an Issue."""
    if isinstance(diagnostic, dict) and diagnostic.get("code"):
        return Issue(
            code=str(diagnostic["code"]),
            source=SOURCE_CONFLUENT,
            title=str(diagnostic.get("title") or "Your simulation could not be set up"),
            message=str(diagnostic.get("message") or ""),
            detail=_trim(diagnostic.get("detail")),
        )
    # Older simulation servers report failures without a structured diagnosis.
    return Issue(
        code="provisioning_failed",
        source=SOURCE_CONFLUENT,
        title="The simulation server could not verify your Confluent cluster",
        message=(
            "The simulation server tried to connect to your Confluent Cloud cluster and write test events, "
            "but the check failed."
        ),
        detail=_trim(fallback_detail),
    )


# ── 3. Confluent Cloud (checked from this laptop) ─────────────────────────────

def classify_confluent_error(
    config: BackendConfig,
    error_names: Iterable[str],
    detail: Optional[str] = None,
) -> Issue:
    """Explain why this backend could not reach or sign in to the Confluent cluster."""
    names = set(error_names)
    bootstrap = config.confluent_bootstrap_server
    detail = _trim(detail)

    if names & _AUTH_ERRORS:
        return Issue(
            code="confluent_auth_failed",
            source=SOURCE_CONFLUENT,
            title="Confluent rejected your API key",
            message=f"The dashboard reached your cluster at {bootstrap}, but Confluent refused the API key and secret.",
            detail=detail,
        )
    if names & _DNS_ERRORS:
        host = (bootstrap or "").split(",")[0].rsplit(":", 1)[0]
        return Issue(
            code="confluent_bootstrap_unresolvable",
            source=SOURCE_CONFLUENT,
            title="Confluent bootstrap server not found",
            message=f"No server called '{host}' could be found.",
            detail=detail,
        )
    if names & _TLS_ERRORS:
        return Issue(
            code="confluent_tls_failed",
            source=SOURCE_CONFLUENT,
            title="Secure connection to Confluent failed",
            message=f"The dashboard could not set up a secure (TLS) connection to {bootstrap}.",
            detail=detail,
        )
    return Issue(
        code="confluent_unreachable",
        source=SOURCE_CONFLUENT,
        title="Could not connect to your Confluent cluster",
        message=(
            f"The dashboard could not open a connection to {bootstrap}. The address or port may be wrong, "
            "or your network is blocking it."
        ),
        detail=detail,
    )


def check_confluent(config: BackendConfig, timeout: float = 6.0) -> Optional[Issue]:
    """
    Blocking: connect to the cluster with the configured credentials and list topics.
    Returns None when it works, otherwise an Issue. Does not create or modify anything.
    Run it with asyncio.to_thread.
    """
    try:
        from confluent_kafka import KafkaException
        from confluent_kafka.admin import AdminClient
    except ImportError:
        return None  # No Kafka client installed; nothing to check.

    errors: List[Any] = []
    client = AdminClient({
        "bootstrap.servers": config.confluent_bootstrap_server,
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": "PLAIN",
        "sasl.username": config.confluent_api_key,
        "sasl.password": config.confluent_api_secret,
        "enable.metrics.push": False,
        "error_cb": errors.append,
    }, logger=_silent_kafka_logger)
    try:
        client.list_topics(timeout=timeout)
        return None
    except KafkaException as exc:
        client.poll(0.5)  # delivers the underlying error (auth, DNS, TLS) to error_cb
        names = [e.name() for e in errors]
        first = str(errors[0]) if errors else str(exc.args[0] if exc.args else exc)
        return classify_confluent_error(config, names, first)
    except Exception as exc:  # e.g. invalid configuration rejected by the client
        return classify_confluent_error(config, [], f"{type(exc).__name__}: {exc}")
