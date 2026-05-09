#!/usr/bin/env python3
"""Generate a static Agent Readiness dashboard from repository assessment data."""

import base64
import json
import logging
import os
import sys
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests
import urllib3
import yaml
from jinja2 import Environment, FileSystemLoader

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

CERTIFICATION_LEVELS = {
    "Platinum": {"min": 90, "color": "#b9f2ff", "text": "#1a1a2e"},
    "Gold": {"min": 75, "color": "#ffd700", "text": "#1a1a2e"},
    "Silver": {"min": 60, "color": "#c0c0c0", "text": "#1a1a2e"},
    "Bronze": {"min": 40, "color": "#cd7f32", "text": "#ffffff"},
    "NeedsImprovement": {"min": 0, "color": "#ff9800", "text": "#ffffff"},
    "None": {"min": -1, "color": "#9e9e9e", "text": "#ffffff"},
}

STATUS_COLORS = {
    "pass": "#4caf50",
    "fail": "#f44336",
    "skipped": "#9e9e9e",
    "error": "#ff9800",
    "not_applicable": "#2196f3",
}

TIER_NAMES = {
    1: "Essential",
    2: "Critical",
    3: "Important",
    4: "Advanced",
}


def load_config(config_path: str = "repos.yaml") -> dict:
    with open(config_path) as f:
        config = yaml.safe_load(f)

    if not config or "repositories" not in config:
        log.error("repos.yaml must contain a 'repositories' list")
        sys.exit(1)

    return config


def fetch_local(repo_config: dict) -> dict | None:
    path = Path(repo_config["path"]) / ".agentready" / "assessment-latest.json"
    if not path.exists():
        log.warning("No assessment data at %s", path)
        return None

    resolved = path.resolve()
    with open(resolved) as f:
        return json.load(f)


def fetch_gitlab(repo_config: dict) -> dict | None:
    project = urllib.parse.quote(repo_config["project"], safe="")
    branch = repo_config.get("branch", "main")
    host = repo_config.get("host", "https://gitlab.com")
    file_path = urllib.parse.quote(".agentready/assessment-latest.json", safe="")

    url = f"{host}/api/v4/projects/{project}/repository/files/{file_path}/raw"
    params = {"ref": branch}

    token = os.environ.get("GITLAB_TOKEN") or os.environ.get("CI_JOB_TOKEN", "")
    headers = {}
    if token:
        headers["PRIVATE-TOKEN"] = token

    verify_ssl = repo_config.get("verify_ssl", True)
    if not verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30, verify=verify_ssl)
        resp.raise_for_status()
        text = resp.text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        if text.endswith(".json"):
            ref_path = urllib.parse.quote(
                f".agentready/{text}", safe=""
            )
            ref_url = f"{host}/api/v4/projects/{project}/repository/files/{ref_path}/raw"
            resp2 = requests.get(ref_url, headers=headers, params=params, timeout=30, verify=verify_ssl)
            resp2.raise_for_status()
            return resp2.json()

        log.warning("Unexpected content from GitLab (%s): %s", repo_config["project"], text[:100])
        return None
    except requests.RequestException as e:
        log.warning("Failed to fetch from GitLab (%s): %s", repo_config["project"], e)
        return None


def fetch_github(repo_config: dict) -> dict | None:
    repo = repo_config["repo"]
    branch = repo_config.get("branch", "main")
    file_path = ".agentready/assessment-latest.json"

    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    params = {"ref": branch}

    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = base64.b64decode(data["content"]).decode("utf-8")
        return json.loads(content)
    except requests.RequestException as e:
        log.warning("Failed to fetch from GitHub (%s): %s", repo, e)
        return None
    except (KeyError, json.JSONDecodeError) as e:
        log.warning("Failed to parse GitHub response (%s): %s", repo, e)
        return None


FETCHERS = {
    "local": fetch_local,
    "gitlab": fetch_gitlab,
    "github": fetch_github,
}


def build_repo_data(repo_config: dict) -> dict:
    repo_type = repo_config.get("type", "local")
    fetcher = FETCHERS.get(repo_type)
    if not fetcher:
        log.warning("Unknown repo type '%s' for %s", repo_type, repo_config["name"])
        return _empty_repo(repo_config)

    assessment = fetcher(repo_config)
    if not assessment:
        return _empty_repo(repo_config)

    findings = assessment.get("findings", [])
    assessed_findings = [f for f in findings if f.get("status") in ("pass", "fail")]
    tiers = {}
    for f in findings:
        if f.get("status") == "not_applicable":
            continue
        tier = f.get("attribute", {}).get("tier", 0)
        tiers.setdefault(tier, []).append(f)

    timestamp_raw = assessment.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(timestamp_raw)
        timestamp_display = ts.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        timestamp_display = timestamp_raw or "—"

    return {
        "name": repo_config["name"],
        "type": repo_type,
        "has_data": True,
        "overall_score": assessment.get("overall_score"),
        "certification_level": assessment.get("certification_level", "None"),
        "timestamp": timestamp_display,
        "attributes_assessed": assessment.get("attributes_assessed", 0),
        "attributes_total": assessment.get("attributes_total", 0),
        "findings": findings,
        "tiers": dict(sorted(tiers.items())),
        "repository": assessment.get("repository", {}),
    }


def _empty_repo(repo_config: dict) -> dict:
    return {
        "name": repo_config["name"],
        "type": repo_config.get("type", "local"),
        "has_data": False,
        "overall_score": None,
        "certification_level": "None",
        "timestamp": "—",
        "attributes_assessed": 0,
        "attributes_total": 0,
        "findings": [],
        "tiers": {},
        "repository": {},
    }


def generate_dashboard(config: dict, output_dir: str = "public"):
    repos_data = []
    for repo_config in config["repositories"]:
        log.info("Fetching assessment for: %s", repo_config["name"])
        repos_data.append(build_repo_data(repo_config))

    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template = env.get_template("dashboard.html.j2")

    html = template.render(
        title=config.get("title", "Agent Readiness Dashboard"),
        org=config.get("org", ""),
        repositories=repos_data,
        certification_levels=CERTIFICATION_LEVELS,
        status_colors=STATUS_COLORS,
        tier_names=TIER_NAMES,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    (out_path / "index.html").write_text(html)
    log.info("Dashboard written to %s/index.html", output_dir)


if __name__ == "__main__":
    config_file = sys.argv[1] if len(sys.argv) > 1 else "repos.yaml"
    cfg = load_config(config_file)
    generate_dashboard(cfg)
