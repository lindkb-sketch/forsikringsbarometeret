#!/usr/bin/env python3
"""Gate GitHub Pages deployment on API-visible artifact for the current run.

GitHub Actions upload-artifact can finish before the artifact listing endpoint
indexes the upload. deploy-pages queries that listing immediately and otherwise
fails with "No artifacts named github-pages were found".
"""
from __future__ import annotations

import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def artifact_is_visible(payload: dict, name: str = "github-pages") -> bool:
    return any(
        item.get("name") == name and not item.get("expired", False)
        for item in payload.get("artifacts", [])
        if isinstance(item, dict)
    )


def wait_for_artifact(
    repository: str,
    run_id: str,
    token: str,
    *,
    attempts: int = 30,
    delay_seconds: float = 4,
    sleep=time.sleep,
    opener=urlopen,
) -> bool:
    if not repository or not run_id or not token:
        raise ValueError("Missing repository, run ID or GitHub Actions token")
    url = f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100"
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "forsikringsbarometeret-pages-visibility",
        },
    )
    for index in range(attempts):
        try:
            with opener(request, timeout=15) as response:
                data = json.load(response)
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f"Cannot enumerate workflow artifacts: {exc}") from exc
        if artifact_is_visible(data):
            print(f"PAGES_ARTIFACT_VISIBLE github-pages on attempt {index + 1}", flush=True)
            return True
        print(f"PAGES_ARTIFACT_PENDING {index + 1}/{attempts}", flush=True)
        if index + 1 < attempts:
            sleep(delay_seconds)
    raise TimeoutError(f"Pages artifact not visible for run {run_id} after {attempts} attempts")


if __name__ == "__main__":
    wait_for_artifact(
        os.environ.get("GITHUB_REPOSITORY", ""),
        os.environ.get("GITHUB_RUN_ID", ""),
        os.environ.get("GITHUB_TOKEN", ""),
    )
