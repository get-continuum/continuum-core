from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import streamlit as st
import yaml


def req(method: str, url: str, *, params: Optional[dict] = None, json_body: Optional[dict] = None) -> requests.Response:
    return requests.request(method, url, params=params, json=json_body, timeout=20)


def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def get_health(base_url: str) -> Tuple[bool, str]:
    try:
        r = req("GET", f"{base_url}/health")
        if r.status_code == 200:
            return True, "ok"
        return False, f"{r.status_code}: {r.text}"
    except Exception as e:
        return False, str(e)


def search_metrics(base_url: str, workspace_id: str, query: str, limit: int = 50) -> List[dict]:
    r = req("GET", f"{base_url}/search", params={"workspace_id": workspace_id, "q": query, "limit": limit})
    if r.status_code != 200:
        raise RuntimeError(f"/search failed: {r.status_code} {r.text}")
    return r.json().get("results", [])


def metric_exists(base_url: str, workspace_id: str, metric_id: str) -> bool:
    r = req("GET", f"{base_url}/metrics/{metric_id}", params={"workspace_id": workspace_id})
    return r.status_code == 200


def get_overlays(base_url: str, workspace_id: str, metric_id: str) -> List[dict]:
    r = req("GET", f"{base_url}/metrics/{metric_id}/overlays", params={"workspace_id": workspace_id})
    if r.status_code == 200:
        return r.json()
    return []


def overlay_exists(existing: List[dict], selector: dict, priority: int) -> bool:
    target = (stable_json(selector or {}), int(priority))
    keys = {(stable_json(o.get("selector") or {}), int(o.get("priority") or 0)) for o in existing}
    return target in keys


def get_history(base_url: str, workspace_id: str, metric_id: str, limit: int = 500) -> List[dict]:
    r = req("GET", f"{base_url}/metrics/{metric_id}/history", params={"workspace_id": workspace_id, "limit": limit})
    if r.status_code == 200:
        return r.json()
    return []


def event_exists(existing: List[dict], candidate: dict) -> bool:
    cand_key = stable_json(
        {
            "event_type": candidate.get("event_type"),
            "source_system": candidate.get("source_system"),
            "source_ref": candidate.get("source_ref") or {},
            "snapshot": candidate.get("snapshot") or {},
        }
    )
    for e in existing:
        e_key = stable_json(
            {
                "event_type": e.get("event_type"),
                "source_system": e.get("source_system"),
                "source_ref": e.get("source_ref") or {},
                "snapshot": e.get("snapshot") or {},
            }
        )
        if e_key == cand_key:
            return True
    return False


def load_demo_yaml(base_url: str, workspace_id: str, yaml_path: str) -> List[str]:
    """
    Idempotent demo loader:
    - metric: skip if exists
    - alias: API upserts by (source_system, source_locator)
    - overlay: skip if same selector+priority exists
    - events: skip if same {event_type, source_system, source_ref, snapshot} exists
    """
    p = Path(yaml_path)
    if not p.exists():
        raise FileNotFoundError(f"YAML not found: {yaml_path}")

    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    metrics = doc.get("metrics") or []
    logs: List[str] = []

    for m in metrics:
        metric_id = m["metric_id"]

        if metric_exists(base_url, workspace_id, metric_id):
            logs.append(f"[{metric_id}] metric exists (skip)")
        else:
            r = req(
                "POST",
                f"{base_url}/metrics",
                params={"workspace_id": workspace_id},
                json_body={
                    "metric_id": metric_id,
                    "canonical_name": m["canonical_name"],
                    "description": m.get("description"),
                },
            )
            if r.status_code != 200:
                raise RuntimeError(f"[{metric_id}] metric create failed: {r.status_code} {r.text}")
            logs.append(f"[{metric_id}] metric created")

        for a in m.get("aliases") or []:
            r = req(
                "POST",
                f"{base_url}/metrics/{metric_id}/aliases",
                params={"workspace_id": workspace_id},
                json_body=a,
            )
            if r.status_code != 200:
                raise RuntimeError(f"[{metric_id}] alias failed: {r.status_code} {r.text}")
            logs.append(f"[{metric_id}] alias ok ({a.get('source_system')}:{a.get('source_locator')})")

        existing_events = get_history(base_url, workspace_id, metric_id, limit=500)
        for e in m.get("events") or []:
            if event_exists(existing_events, e):
                logs.append(f"[{metric_id}] event exists (skip) ({e.get('event_type')})")
                continue
            r = req(
                "POST",
                f"{base_url}/metrics/{metric_id}/events",
                params={"workspace_id": workspace_id},
                json_body=e,
            )
            if r.status_code != 200:
                raise RuntimeError(f"[{metric_id}] event failed: {r.status_code} {r.text}")
            out = r.json()
            logs.append(f"[{metric_id}] event appended v{out.get('version_id')} ({e.get('event_type')})")

        existing_overlays = get_overlays(base_url, workspace_id, metric_id)
        for o in m.get("overlays") or []:
            selector = o.get("selector") or {}
            priority = int(o.get("priority") or 0)
            if overlay_exists(existing_overlays, selector, priority):
                logs.append(f"[{metric_id}] overlay exists (skip) selector={selector} priority={priority}")
                continue
            r = req(
                "POST",
                f"{base_url}/metrics/{metric_id}/overlays",
                params={"workspace_id": workspace_id},
                json_body=o,
            )
            if r.status_code != 200:
                raise RuntimeError(f"[{metric_id}] overlay failed: {r.status_code} {r.text}")
            out = r.json()
            logs.append(f"[{metric_id}] overlay created {out.get('overlay_id')} priority={priority}")

    return logs


def parse_context_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except Exception as e:
        raise ValueError(f"Invalid JSON: {e}")
    if not isinstance(obj, dict):
        raise ValueError("Context JSON must be an object (e.g. {\"team\":\"marketing\"})")
    return obj


st.set_page_config(page_title="Engram Semantic — Memory Core Demo", layout="centered")
st.title("Engram Semantic — Memory Core Demo")

with st.sidebar:
    st.subheader("Connection")
    base_url = st.text_input("base_url", value="http://127.0.0.1:8000")
    workspace_id = st.text_input("workspace_id", value="default")

    ok, msg = get_health(base_url.rstrip("/"))
    st.caption(f"health: {'ok' if ok else 'error'} ({msg})")

    st.subheader("Demo loader")
    demo_yaml_path = st.text_input("demo YAML path", value="demo/demo.yaml")
    if st.button("Load demo YAML", use_container_width=True):
        try:
            logs = load_demo_yaml(base_url.rstrip("/"), workspace_id, demo_yaml_path)
            st.success("Loaded demo YAML.")
            with st.expander("Loader logs", expanded=True):
                st.code("\n".join(logs))
        except Exception as e:
            st.error(str(e))

st.subheader("Pick a metric")
search_query = st.text_input("Search query (uses /search)", value="rev")

metrics: List[dict] = []
try:
    if search_query.strip():
        metrics = search_metrics(base_url.rstrip("/"), workspace_id, search_query.strip(), limit=50)
except Exception as e:
    st.warning(f"Search error: {e}")

metric_options = [m["metric_id"] for m in metrics if "metric_id" in m]
selected_metric_id = st.selectbox("metric_id", options=metric_options or ["revenue"], index=0)

st.subheader("Context")

col1, col2 = st.columns(2)
with col1:
    team = st.text_input("team", value="marketing")
with col2:
    use_case = st.text_input("use_case", value="weekly_performance")

context_json_raw = st.text_area(
    "Additional context JSON (optional)",
    value="{}",
    height=120,
    help='Merged into context. Must be a JSON object, e.g. {"region":"us"}',
)

ctx: Dict[str, Any] = {}
if team.strip():
    ctx["team"] = team.strip()
if use_case.strip():
    ctx["use_case"] = use_case.strip()
try:
    ctx_extra = parse_context_json(context_json_raw)
    ctx.update(ctx_extra)
except Exception as e:
    st.error(str(e))

st.subheader("Resolve")
if st.button("Resolve", type="primary", use_container_width=True):
    try:
        r = req(
            "POST",
            f"{base_url.rstrip('/')}/metrics/{selected_metric_id}/resolve",
            params={"workspace_id": workspace_id},
            json_body={"context": ctx},
        )
        if r.status_code != 200:
            st.error(f"Resolve failed: {r.status_code} {r.text}")
        else:
            out = r.json()
            st.success("Resolved.")

            st.markdown("**applied_overlays**")
            st.code(json.dumps(out.get("applied_overlays", []), indent=2))

            st.markdown("**provenance**")
            st.json(out.get("provenance", {}))

            st.markdown("**resolved_snapshot**")
            st.json(out.get("resolved_snapshot", {}))
    except Exception as e:
        st.error(str(e))

