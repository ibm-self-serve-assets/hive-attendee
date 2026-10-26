import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional, List, Any, Dict, Tuple

import httpx
from fastapi import FastAPI, Request, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend import connection_issues as ci
from backend.config import BackendConfig
from backend.log_setup import LOG_FILE, MAJOR
from backend.store import DashboardStore
from backend.consumer import EventConsumerManager, CalculatedValuesConsumer, InventoryBalancesConsumer
from backend.topic_watch import CalculatedValuesWatcher, InventoryBalancesWatcher, EventTopicsWatcher

logger = logging.getLogger("hive.backend")

config: BackendConfig = BackendConfig.load_from_env()
store: DashboardStore = DashboardStore()
consumer_mgr: Optional[EventConsumerManager] = None
event_topics_watcher: Optional[EventTopicsWatcher] = None
hive_job_durations_watcher: Optional[CalculatedValuesWatcher] = None
hive_job_durations_consumer: Optional[CalculatedValuesConsumer] = None
hive_inventory_balances_watcher: Optional[InventoryBalancesWatcher] = None
hive_inventory_balances_consumer: Optional[InventoryBalancesConsumer] = None
subscribers: List[asyncio.Queue] = []


async def notify_subscribers(snap: Dict[str, Any]):
    data = json.dumps(snap)
    for q in list(subscribers):
        try:
            q.put_nowait(data)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    global consumer_mgr, event_topics_watcher, \
        hive_job_durations_watcher, hive_job_durations_consumer, \
        hive_inventory_balances_watcher, hive_inventory_balances_consumer
    store.attendee_id = config.attendee_id
    logger.info(
        f"Console shows only major events and errors. Full logs: {LOG_FILE}",
        extra=MAJOR,
    )

    consumer_mgr = EventConsumerManager(
        store=store,
        bootstrap_servers=config.confluent_bootstrap_server,
        api_key=config.confluent_api_key,
        api_secret=config.confluent_api_secret,
        on_event_callback=notify_subscribers,
    )
    consumer_mgr.start()

    async def _notify_state():
        await notify_subscribers(store.snapshot())

    event_topics_watcher = EventTopicsWatcher(
        store=store,
        bootstrap_servers=config.confluent_bootstrap_server,
        api_key=config.confluent_api_key,
        api_secret=config.confluent_api_secret,
        on_change=_notify_state,
    )
    event_topics_watcher.start()

    hive_job_durations_watcher = CalculatedValuesWatcher(
        store=store,
        bootstrap_servers=config.confluent_bootstrap_server,
        api_key=config.confluent_api_key,
        api_secret=config.confluent_api_secret,
        on_change=_notify_state,
    )
    hive_job_durations_watcher.start()

    hive_job_durations_consumer = CalculatedValuesConsumer(
        store=store,
        bootstrap_servers=config.confluent_bootstrap_server,
        api_key=config.confluent_api_key,
        api_secret=config.confluent_api_secret,
        on_change=_notify_state,
    )
    hive_job_durations_consumer.start()

    hive_inventory_balances_watcher = InventoryBalancesWatcher(
        store=store,
        bootstrap_servers=config.confluent_bootstrap_server,
        api_key=config.confluent_api_key,
        api_secret=config.confluent_api_secret,
        on_change=_notify_state,
    )
    hive_inventory_balances_watcher.start()

    hive_inventory_balances_consumer = InventoryBalancesConsumer(
        store=store,
        bootstrap_servers=config.confluent_bootstrap_server,
        api_key=config.confluent_api_key,
        api_secret=config.confluent_api_secret,
        on_change=_notify_state,
    )
    hive_inventory_balances_consumer.start()

    asyncio.create_task(auto_connect())
    yield
    event_topics_watcher.stop()
    hive_job_durations_watcher.stop()
    if hive_job_durations_consumer:
        hive_job_durations_consumer.stop()
    if hive_inventory_balances_watcher:
        hive_inventory_balances_watcher.stop()
    if hive_inventory_balances_consumer:
        hive_inventory_balances_consumer.stop()
    if consumer_mgr:
        consumer_mgr.stop()


PROVISION_WAIT_SECONDS = 45
_connect_lock = asyncio.Lock()


async def _set_connection(conn_status: str, issues: Optional[List[ci.Issue]] = None) -> None:
    """Record the connection state, log any problems to the console, and tell the dashboard."""
    issues = issues or []
    store.connection_status = conn_status
    store.connection_issues = [i.to_dict() for i in issues]
    for issue in issues:
        logger.error("\n" + ci.format_for_console(issue))
    await notify_subscribers(store.snapshot())


def _response_body(r: httpx.Response) -> Any:
    try:
        return r.json()
    except ValueError:
        return r.text


def _connect_failure_message(default: str) -> str:
    """Plain-language reason the last connection attempt failed, for command error replies."""
    if store.connection_issues:
        first = store.connection_issues[0]
        return f"{first['title']}. {first['message']}" if first.get("message") else first["title"]
    return default


async def _check_sim_server(
    client: httpx.AsyncClient, headers: Dict[str, str]
) -> Tuple[Optional[str], Optional[ci.Issue]]:
    """Confirm the URL, access token and attendee ID by asking the server for its epoch."""
    try:
        r = await client.get(f"{config.simulation_server_url}/v1/server", headers=headers)
    except (httpx.RequestError, httpx.InvalidURL) as e:
        return None, ci.classify_network_error(config, e)
    if r.status_code >= 400:
        return None, ci.classify_http_error(config, r.status_code, _response_body(r))
    body = _response_body(r)
    epoch = body.get("server_epoch") if isinstance(body, dict) else None
    if not epoch:
        return None, ci.not_a_simulation_server(config)
    return epoch, None


async def _wait_for_provisioning(
    client: httpx.AsyncClient, headers: Dict[str, str]
) -> Tuple[Optional[Dict[str, Any]], Optional[ci.Issue]]:
    """
    Poll until the server's verification of the Confluent cluster finishes.
    Returns (simulation detail, None) when ready, or (None, Issue) when it failed or timed out.
    """
    deadline = time.monotonic() + PROVISION_WAIT_SECONDS
    while time.monotonic() < deadline:
        await asyncio.sleep(0.25)
        r = await client.get(
            f"{config.simulation_server_url}/v1/simulations/{store.active_simulation_id}",
            headers=headers,
        )
        if r.status_code != 200:
            continue
        data = r.json()
        lifecycle = data.get("lifecycle_status")
        if lifecycle == "provisioning_failed":
            return None, ci.from_server_diagnostic(data.get("provisioning_error"))
        if lifecycle not in ("provisioning", None):
            return data, None
    return None, ci.provisioning_timeout(config, PROVISION_WAIT_SECONDS)


async def auto_connect():
    # One attempt at a time; a caller that arrives mid-attempt waits for it, then runs again.
    async with _connect_lock:
        await _auto_connect()


async def _auto_connect():
    global consumer_mgr
    store.attendee_id = config.attendee_id
    await _set_connection("connecting")

    config_issues = ci.validate_config(config)
    if config_issues:
        await _set_connection("failed", config_issues)
        return

    headers = {"Authorization": f"Bearer {config.workshop_access_token}"}
    if config.attendee_id:
        headers["X-Attendee-Id"] = config.attendee_id

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check both ends before provisioning, and report everything that is wrong at once.
            epoch, server_issue = await _check_sim_server(client, headers)
            confluent_issue = await asyncio.to_thread(ci.check_confluent, config)
            problems = [i for i in (server_issue, confluent_issue) if i]
            if problems:
                await _set_connection("failed", problems)
                return
            store.server_epoch = epoch

            # Find or provision simulation
            topics_map: Dict[str, str] = {}
            wait_for_ready = False
            f_resp = await client.get(f"{config.simulation_server_url}/v1/simulations", headers=headers)
            if f_resp.status_code == 200:
                facts = f_resp.json().get("simulations", [])
                if facts:
                    f0 = facts[0]
                    f0_status = f0.get("lifecycle_status")
                    if f0_status in ("expired", "provisioning_failed"):
                        logger.info(f"AUTO-CONNECT: Simulation {f0['simulation_id'][:8]} is {f0_status}; will provision fresh simulation", extra=MAJOR)
                        store.active_simulation_id = None
                    else:
                        store.active_simulation_id = f0["simulation_id"]
                        store.server_epoch = f0["server_epoch"]
                        store.lifecycle_status = f0_status or store.lifecycle_status
                        store.running = f0.get("running", store.running)
                        topics_map = f0.get("topics", {})
                        wait_for_ready = f0_status == "provisioning"
                        logger.info(f"AUTO-CONNECT: Reconnected to simulation {f0['simulation_id'][:8]}…", extra=MAJOR)

            if not store.active_simulation_id:
                logger.info("AUTO-CONNECT: Provisioning new simulation…", extra=MAJOR)
                prov_body: Dict[str, Any] = {
                    "bootstrap_server": config.confluent_bootstrap_server,
                    "producer_credentials": {
                        "api_key": config.confluent_api_key,
                        "api_secret": config.confluent_api_secret,
                    },
                }
                if config.attendee_id:
                    prov_body["attendee_id"] = config.attendee_id
                prov_r = await client.post(
                    f"{config.simulation_server_url}/v1/simulations",
                    json=prov_body,
                    headers={
                        **headers,
                        "Idempotency-Key": str(uuid.uuid4()),
                        "X-Server-Epoch": epoch,
                    },
                )
                prov_r.raise_for_status()
                prov_data = prov_r.json()
                store.active_simulation_id = prov_data["simulation_id"]
                store.reset()
                wait_for_ready = True
                logger.info(f"AUTO-CONNECT: Simulation provisioned {store.active_simulation_id[:8]}… waiting for probe verification", extra=MAJOR)

            if wait_for_ready:
                ready, issue = await _wait_for_provisioning(client, headers)
                if issue:
                    store.active_simulation_id = None
                    await _set_connection("failed", [issue])
                    return
                topics_map = ready.get("topics", {})
                store.lifecycle_status = ready["lifecycle_status"]
                store.running = (store.lifecycle_status == "running")
                logger.info(f"AUTO-CONNECT: Simulation ready with status '{store.lifecycle_status}'", extra=MAJOR)

            if topics_map:
                topic_list = list(topics_map.values())
                if consumer_mgr:
                    consumer_mgr.stop()
                consumer_mgr = EventConsumerManager(
                    store=store,
                    bootstrap_servers=config.confluent_bootstrap_server,
                    api_key=config.confluent_api_key,
                    api_secret=config.confluent_api_secret,
                    topics=topic_list,
                    on_event_callback=notify_subscribers,
                )
                consumer_mgr.start()
                logger.info(f"AUTO-CONNECT: Consumer started on {len(topic_list)} topics", extra=MAJOR)
            else:
                logger.warning("AUTO-CONNECT: No topics — consumer not started")

            await _set_connection("connected")

    except httpx.HTTPStatusError as e:
        issue = ci.classify_http_error(config, e.response.status_code, _response_body(e.response))
        await _set_connection("failed", [issue])
    except Exception as e:
        await _set_connection("failed", [ci.classify_network_error(config, e)])


app = FastAPI(title="Hive Connect-Simulation Backend", version="1.0.0", lifespan=lifespan)

allowed_origins = [
    f"http://localhost:{config.local_frontend_port}",
    f"http://127.0.0.1:{config.local_frontend_port}",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ControlCommandRequest(BaseModel):
    command: str
    start: Optional[bool] = True
    expected_generation: Optional[int] = None


@app.get("/api/config")
async def get_config():
    return {"fully_configured": not ci.validate_config(config)}


@app.get("/api/status")
async def get_status():
    return store.snapshot()


@app.post("/api/controls")
async def send_control(
    req: ControlCommandRequest,
):
    if not config.workshop_access_token:
        raise HTTPException(status_code=400, detail={
            "error_code": "not_connected",
            "message": _connect_failure_message("WORKSHOP_ACCESS_TOKEN is not set in spec-shared/.env."),
        })

    if req.command not in ("start", "pause", "stop", "restart"):
        raise HTTPException(status_code=422, detail="Invalid command")

    if not store.active_simulation_id:
        if req.command == "restart":
            logger.info("Restart requested with no active simulation; provisioning fresh simulation...", extra=MAJOR)
            await auto_connect()
            if not store.active_simulation_id:
                raise HTTPException(status_code=500, detail={
                    "error_code": "provision_failed",
                    "message": _connect_failure_message("Failed to provision new simulation"),
                })
            if req.start is not False:
                return await _send_server_command("start")
            return {"lifecycle_status": store.lifecycle_status, "simulation_id": store.active_simulation_id}
        raise HTTPException(status_code=400, detail={
            "error_code": "not_connected",
            "message": _connect_failure_message("No active simulation. Restart the backend."),
        })

    cmd_url = f"{config.simulation_server_url}/v1/simulations/{store.active_simulation_id}/{req.command}"
    headers = {
        "Authorization": f"Bearer {config.workshop_access_token}",
        "Idempotency-Key": str(uuid.uuid4()),
        "X-Server-Epoch": store.server_epoch or "",
    }
    if config.attendee_id:
        headers["X-Attendee-Id"] = config.attendee_id
    body: Dict[str, Any] = {}
    if req.expected_generation is not None:
        body["expected_generation"] = req.expected_generation
    elif store.run_generation > 0:
        body["expected_generation"] = store.run_generation
    if req.command == "restart":
        body["start"] = req.start if req.start is not None else True

    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(cmd_url, json=body, headers=headers)
        if (r.status_code in (404, 409)) or (r.status_code == 410 and req.command == "restart"):
            logger.info(f"Server returned {r.status_code}; refreshing connection and active simulation...", extra=MAJOR)
            store.active_simulation_id = None
            await auto_connect()
            if not store.active_simulation_id:
                raise HTTPException(status_code=500, detail={
                    "error_code": "provision_failed",
                    "message": _connect_failure_message("Failed to re-sync simulation after server reload/restart"),
                })
            target_cmd = "start" if (req.command == "restart" and req.start is not False) or req.command == "start" else req.command
            return await _send_server_command(target_cmd)

        if r.status_code >= 400:
            try:
                err_body = r.json()
            except Exception:
                err_body = {"message": r.text or f"HTTP {r.status_code}"}
            raise HTTPException(status_code=r.status_code, detail=err_body)

        receipt = r.json()
        if "lifecycle_status" in receipt:
            store.lifecycle_status = receipt["lifecycle_status"]
            store.running = (store.lifecycle_status == "running")
            await notify_subscribers(store.snapshot())
        return receipt


async def _send_server_command(command: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cmd_url = f"{config.simulation_server_url}/v1/simulations/{store.active_simulation_id}/{command}"
    headers = {
        "Authorization": f"Bearer {config.workshop_access_token}",
        "Idempotency-Key": str(uuid.uuid4()),
        "X-Server-Epoch": store.server_epoch or "",
    }
    if config.attendee_id:
        headers["X-Attendee-Id"] = config.attendee_id
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.post(cmd_url, json=body or {}, headers=headers)
        if r.status_code >= 400:
            try:
                err_body = r.json()
            except Exception:
                err_body = {"message": r.text or f"HTTP {r.status_code}"}
            raise HTTPException(status_code=r.status_code, detail=err_body)

        receipt = r.json()
        if "lifecycle_status" in receipt:
            store.lifecycle_status = receipt["lifecycle_status"]
            store.running = (store.lifecycle_status == "running")
            await notify_subscribers(store.snapshot())
        return receipt


@app.get("/api/stream")
async def event_stream(request: Request):
    queue: asyncio.Queue = asyncio.Queue()
    subscribers.append(queue)

    async def generate():
        # Send initial snapshot
        initial = {"type": "init", "state": store.snapshot()}
        yield f"data: {json.dumps(initial)}\n\n"

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps({'type': 'update', 'state': json.loads(data)})}\n\n"
                except asyncio.TimeoutError:
                    hb = {"type": "heartbeat", "state": store.snapshot()}
                    yield f"data: {json.dumps(hb)}\n\n"
        finally:
            if queue in subscribers:
                subscribers.remove(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
