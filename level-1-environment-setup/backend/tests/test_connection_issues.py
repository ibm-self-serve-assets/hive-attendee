import httpx
import pytest

from backend import connection_issues as ci
from backend.config import BackendConfig, is_placeholder


def make_config(**overrides) -> BackendConfig:
    base = dict(
        simulation_server_url="https://sim.example.com",
        workshop_access_token="tok-123",
        attendee_id="queen-1",
        confluent_bootstrap_server="pkc-abc12.us-west1.gcp.confluent.cloud:9092",
        confluent_api_key="KEY",
        confluent_api_secret="SECRET",
    )
    base.update(overrides)
    return BackendConfig(**base)


def codes(issues):
    return [i.code for i in issues]


# ── config loading ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value", ["CHANGE_ME", "<token_id>", "<attendee_id>", "your-attendee-id", "provided-by-the-intructor"])
def test_template_values_are_placeholders(value):
    assert is_placeholder(value)


@pytest.mark.parametrize("value", ["queen-042", "https://sim.example.com", "pkc-1.cloud:9092", "", None])
def test_real_values_are_not_placeholders(value):
    assert not is_placeholder(value)


def test_load_from_env_flags_placeholders(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "SIMULATION_SERVER_URL=provided-by-the-intructor\n"
        "WORKSHOP_ACCESS_TOKEN=<token_id>\n"
        "ATTENDEE_ID=queen-1\n"
        "CONFLUENT_BOOTSTRAP_SERVER=CHANGE_ME\n"
        "CONFLUENT_API_KEY=KEY\n"
        "CONFLUENT_API_SECRET=SECRET\n"
    )
    for name in ("SIMULATION_SERVER_URL", "WORKSHOP_ACCESS_TOKEN", "ATTENDEE_ID",
                 "CONFLUENT_BOOTSTRAP_SERVER", "CONFLUENT_API_KEY", "CONFLUENT_API_SECRET"):
        monkeypatch.delenv(name, raising=False)
    cfg = BackendConfig.load_from_env(str(env))
    assert cfg.workshop_access_token is None
    assert cfg.confluent_bootstrap_server is None
    assert cfg.attendee_id == "queen-1"
    assert set(cfg.placeholder_vars) == {"SIMULATION_SERVER_URL", "WORKSHOP_ACCESS_TOKEN", "CONFLUENT_BOOTSTRAP_SERVER"}


def test_unset_simulation_url_uses_default(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("ATTENDEE_ID=queen-1\n")
    monkeypatch.delenv("SIMULATION_SERVER_URL", raising=False)
    cfg = BackendConfig.load_from_env(str(env))
    assert cfg.simulation_server_url == "http://localhost:8080"
    assert cfg.simulation_server_url_is_default


# ── validate_config ───────────────────────────────────────────────────────────

def test_valid_config_has_no_issues():
    assert ci.validate_config(make_config()) == []


def test_unfilled_simulation_url():
    cfg = make_config(simulation_server_url="provided-by-the-intructor", placeholder_vars=["SIMULATION_SERVER_URL"])
    assert codes(ci.validate_config(cfg)) == ["sim_url_not_set"]


@pytest.mark.parametrize("url", ["sim.example.com", "ftp://sim.example.com", "https://", "htp://typo.com"])
def test_invalid_simulation_url(url):
    issues = ci.validate_config(make_config(simulation_server_url=url))
    assert codes(issues) == ["sim_url_invalid"]
    assert "SIMULATION_SERVER_URL" in issues[0].title


def test_missing_token():
    issues = ci.validate_config(make_config(workshop_access_token=None))
    assert codes(issues) == ["token_missing"]


@pytest.mark.parametrize("bootstrap", [
    "https://pkc-abc12.us-west1.gcp.confluent.cloud:9092",
    "pkc-abc12.us-west1.gcp.confluent.cloud",
    "pkc abc:9092",
])
def test_invalid_bootstrap_format(bootstrap):
    issues = ci.validate_config(make_config(confluent_bootstrap_server=bootstrap))
    assert codes(issues) == ["confluent_bootstrap_invalid"]


def test_missing_bootstrap():
    assert codes(ci.validate_config(make_config(confluent_bootstrap_server=None))) == ["confluent_bootstrap_missing"]


def test_missing_secret_names_only_that_variable():
    issues = ci.validate_config(make_config(confluent_api_secret=None))
    assert codes(issues) == ["confluent_credentials_missing"]
    assert "CONFLUENT_API_SECRET" in issues[0].message
    assert "CONFLUENT_API_KEY" not in issues[0].message


def test_everything_wrong_reports_everything():
    cfg = make_config(workshop_access_token=None, confluent_bootstrap_server=None,
                      confluent_api_key=None, confluent_api_secret=None)
    assert set(codes(ci.validate_config(cfg))) == {
        "token_missing", "confluent_bootstrap_missing", "confluent_credentials_missing",
    }


# ── simulation-server HTTP errors ─────────────────────────────────────────────

def body(code, message):
    return {"detail": {"error_code": code, "message": message}}


def test_bad_token_shows_the_servers_message():
    issue = ci.classify_http_error(make_config(), 401, body("unauthorized", "Invalid workshop access token"))
    assert issue.code == "token_rejected"
    assert issue.title == "Invalid workshop access token"
    assert issue.message == ""


def test_attendee_not_enrolled():
    issue = ci.classify_http_error(make_config(), 401, body("unauthorized", "Attendee not enrolled"))
    assert issue.code == "attendee_not_enrolled"
    assert issue.title == "Attendee not enrolled"


def test_attendee_id_mismatch_shows_the_servers_message_unchanged():
    server_message = "Attendee ID 'queen-9' does not match access token (belongs to 'queen-1')"
    issue = ci.classify_http_error(
        make_config(attendee_id="queen-9"), 403, body("attendee_token_mismatch", server_message),
    )
    assert issue.code == "attendee_id_mismatch"
    assert issue.title == server_message
    assert issue.message == "" and issue.detail is None


def test_wrong_service_at_url_has_no_server_message_so_states_the_status():
    issue = ci.classify_http_error(make_config(), 404, "<html>Not Found</html>")
    assert issue.code == "sim_url_wrong_service"
    assert "HTTP 404" in issue.title and "sim.example.com" in issue.title
    assert issue.detail == "<html>Not Found</html>"


def test_server_unavailable():
    issue = ci.classify_http_error(make_config(), 503, "")
    assert issue.code == "sim_server_unavailable"
    assert "HTTP 503" in issue.title


def test_unknown_status_shows_the_servers_message():
    issue = ci.classify_http_error(make_config(), 500, body("boom", "internal"))
    assert issue.code == "sim_server_error"
    assert issue.title == "internal"


# ── simulation-server network errors ──────────────────────────────────────────

def test_dns_failure():
    exc = httpx.ConnectError("[Errno 8] nodename nor servname provided, or not known")
    assert ci.classify_network_error(make_config(), exc).code == "sim_host_not_found"


def test_connection_refused_on_default_url_mentions_it_is_the_default():
    cfg = make_config(simulation_server_url="http://localhost:8080", simulation_server_url_is_default=True)
    issue = ci.classify_network_error(cfg, httpx.ConnectError("[Errno 61] Connection refused"))
    assert issue.code == "sim_unreachable"
    assert "SIMULATION_SERVER_URL is not set" in issue.message


def test_timeout():
    assert ci.classify_network_error(make_config(), httpx.ConnectTimeout("timed out")).code == "sim_timeout"


def test_unsupported_protocol():
    exc = httpx.UnsupportedProtocol("Request URL is missing an 'http://' or 'https://' protocol.")
    assert ci.classify_network_error(make_config(), exc).code == "sim_url_invalid"


def test_tls_error():
    exc = httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
    assert ci.classify_network_error(make_config(), exc).code == "sim_tls_failed"


# ── Confluent errors ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("names,expected", [
    (["_AUTHENTICATION", "_ALL_BROKERS_DOWN"], "confluent_auth_failed"),
    (["_RESOLVE", "_ALL_BROKERS_DOWN"], "confluent_bootstrap_unresolvable"),
    (["_SSL"], "confluent_tls_failed"),
    (["_TRANSPORT", "_ALL_BROKERS_DOWN"], "confluent_unreachable"),
    ([], "confluent_unreachable"),
])
def test_classify_confluent_error(names, expected):
    assert ci.classify_confluent_error(make_config(), names).code == expected


def test_check_confluent_reports_unresolvable_host():
    cfg = make_config(confluent_bootstrap_server="pkc-does-not-exist.invalid:9092")
    issue = ci.check_confluent(cfg, timeout=4.0)
    assert issue is not None
    assert issue.code == "confluent_bootstrap_unresolvable"
    assert "pkc-does-not-exist.invalid" in issue.message


# ── server-supplied diagnosis ─────────────────────────────────────────────────

def test_server_diagnostic_is_passed_through():
    diag = {"code": "confluent_topics_missing", "title": "Topics missing", "message": "Missing: a, b",
            "detail": None}
    issue = ci.from_server_diagnostic(diag)
    assert (issue.code, issue.title, issue.message) == ("confluent_topics_missing", "Topics missing", "Missing: a, b")


def test_missing_server_diagnostic_still_reports_a_provisioning_failure():
    issue = ci.from_server_diagnostic(None)
    assert issue.code == "provisioning_failed"
    assert issue.title and issue.message


# ── output never leaks secrets ────────────────────────────────────────────────

def test_console_block_is_readable_and_secret_free():
    cfg = make_config(
        confluent_bootstrap_server="bad host:9092",
        workshop_access_token="tok-s3cr3t-value",
        confluent_api_key="key-s3cr3t-value",
        confluent_api_secret="sec-s3cr3t-value",
    )
    issues = ci.validate_config(cfg) + [ci.classify_http_error(cfg, 401, body("unauthorized", "Invalid"))]
    issues.append(ci.classify_confluent_error(cfg, ["_AUTHENTICATION"], "SASL authentication error"))
    text = "\n".join(ci.format_for_console(i) for i in issues)
    assert "What happened:" in text and "Settings:" not in text
    assert "How to fix" not in text
    assert "s3cr3t" not in text
