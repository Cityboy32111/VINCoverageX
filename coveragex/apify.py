"""Minimal Apify REST client (no extra SDK dependency).

Apify is the COLLECTION engine: dealer discovery + dynamic inventory pages.
Token is read from config/.env (APIFY_TOKEN) and sent as a Bearer header so
it never appears in a URL/log. Network-dependent; raises ApifyError with a
clear message if the host is blocked by the environment network policy.

Before using any actor (per phase1_plan.md): check input schema, pricing,
output fields, source-terms risk; test on 3 dealers; save raw sample; map to
schema; log the run.
"""
from __future__ import annotations

import time

import requests

from .config import require_env

API_BASE = "https://api.apify.com/v2"
_TIMEOUT = 60


class ApifyError(RuntimeError):
    pass


class ApifyClient:
    def __init__(self, token: str | None = None):
        self.token = token or require_env("APIFY_TOKEN")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "User-Agent": "CoverageX-SignalGraph/0.1 (PoC)",
        })

    def _check(self, r: requests.Response) -> None:
        if r.status_code == 403 and r.headers.get("x-deny-reason"):
            raise ApifyError(
                f"403 host_not_allowed from Apify ({r.headers.get('x-deny-reason')}). "
                f"The environment network policy is blocking api.apify.com. "
                f"Allow api.apify.com (and dealer hosts) or run locally with config/.env."
            )
        if not r.ok:
            raise ApifyError(f"Apify HTTP {r.status_code}: {r.text[:300]}")

    def run_actor(self, actor_id: str, run_input: dict, *, poll_interval: int = 10,
                  timeout: int = 1800) -> tuple[list[dict], dict]:
        """Start an actor run, poll to completion, return (items, run_meta)."""
        r = self.session.post(f"{API_BASE}/acts/{actor_id}/runs",
                              json=run_input, timeout=_TIMEOUT)
        self._check(r)
        run = r.json()["data"]
        run_id = run["id"]
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(poll_interval)
            s = self.session.get(f"{API_BASE}/actor-runs/{run_id}", timeout=_TIMEOUT)
            self._check(s)
            run = s.json()["data"]
            status = run["status"]
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                break
        if run["status"] != "SUCCEEDED":
            raise ApifyError(f"Actor run {run_id} ended with status {run['status']}")
        items = self.get_dataset_items(run["defaultDatasetId"])
        return items, run

    def run_actor_sync(self, actor_id: str, run_input: dict, timeout: int = 300) -> list[dict]:
        """Run a fast actor synchronously and return dataset items directly."""
        r = self.session.post(
            f"{API_BASE}/acts/{actor_id}/run-sync-get-dataset-items",
            json=run_input, timeout=timeout + 30,
        )
        self._check(r)
        return r.json()

    def get_dataset_items(self, dataset_id: str) -> list[dict]:
        r = self.session.get(
            f"{API_BASE}/datasets/{dataset_id}/items",
            params={"clean": "true", "format": "json"}, timeout=_TIMEOUT,
        )
        self._check(r)
        return r.json()
