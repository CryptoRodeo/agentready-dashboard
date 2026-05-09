# AgentReady Dashboard

A static dashboard that aggregates [AgentReady](https://github.com/ambient-code/agentready) assessment scores across your repositories into a single view. Track how well your codebases are prepared for AI-assisted development — at a glance, across teams.

## Why

AI coding agents (Claude Code, Copilot, Cursor, etc.) work dramatically better in well-structured repositories. AgentReady assesses repos against a tiered rubric of best practices — but scores sitting in individual repos are hard to compare, track, or act on at scale.

This dashboard solves that by:

- **Centralizing visibility** — one page shows every repo's readiness score, certification level, and trend
- **Highlighting gaps** — expandable per-repo detail surfaces failing checks with remediation steps and commands
- **Requiring zero infrastructure** — generates a single static HTML file; deploy to GitLab Pages, GitHub Pages, or any static host
- **Staying current automatically** — CI pipelines regenerate on push and on a schedule (every 6 hours by default)

## Features

- **Certification tiers** — Platinum (90+), Gold (75+), Silver (60+), Bronze (40+), Needs Improvement
- **Tiered findings** — Essential, Critical, Important, Advanced — so you know what to fix first
- **Multi-source** — pull assessments from GitLab (including self-hosted), GitHub, or local filesystem
- **Dark/light mode** — respects system preference
- **Sortable & interactive** — click columns to sort, click rows to drill into findings, evidence, and remediation
- **Responsive** — works on mobile

## Quick Start

```bash
pip install -r requirements.txt

# Edit repos.yaml with your repositories (see Configuration below)

python generate.py
open public/index.html
```

## Setup

1. Fork or clone this repo
2. Edit `repos.yaml`:

```yaml
title: "My Team's Agent Readiness"
org: "Platform Engineering"

repositories:
  - name: my-app
    type: gitlab
    project: my-group/my-app       # GitLab project path
    branch: main

  - name: my-oss-lib
    type: github
    repo: my-org/my-oss-lib        # GitHub owner/repo

  - name: local-service
    type: local
    path: /home/user/projects/svc  # Absolute path
```

3. Set tokens for private repos:

   | Platform | Env var | Scope needed |
   |----------|---------|--------------|
   | GitLab | `GITLAB_TOKEN` | `read_api` |
   | GitHub | `GITHUB_TOKEN` | `repo` |

   Public repos and same-instance GitLab CI jobs may not need tokens.

4. Push to your default branch — CI generates and deploys the dashboard

### CI/CD

Both GitLab CI (`.gitlab-ci.yml`) and GitHub Actions (`.github/workflows/pages.yml`) configs are included. GitHub Actions runs on push to `main`, every 6 hours, and on manual dispatch.

## Configuration

### Repository types

| Type | Required fields | Auth env var |
|------|----------------|--------------|
| `gitlab` | `project` (e.g., `group/subgroup/repo`) | `GITLAB_TOKEN` or `CI_JOB_TOKEN` |
| `github` | `repo` (e.g., `owner/repo`) | `GITHUB_TOKEN` |
| `local` | `path` (absolute filesystem path) | — |

### Optional fields

- `branch` — branch to read from (default: `main`)
- `host` — GitLab instance URL for self-hosted (default: `https://gitlab.com`)

## How It Works

1. `generate.py` reads `repos.yaml`
2. For each repo, fetches `.agentready/assessment-latest.json` via API (or filesystem)
3. Renders a single static HTML dashboard to `public/index.html` using Jinja2
4. CI deploys `public/` to your pages host

Repos without assessment data show as "None" — run `agentready assess <repo-path>` to generate data.

## Requirements

- Python 3.10+
- Dependencies: `jinja2`, `requests`, `pyyaml`
