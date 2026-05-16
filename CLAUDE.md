# AgentReady Fleet

Static dashboard generator that aggregates AgentReady assessment scores across repositories.

## Architecture

- `generate.py` — single-file dashboard generator (Python 3.10+)
- `templates/dashboard.html.j2` — Jinja2 template for the HTML dashboard
- `repos.yaml` — configuration listing repositories to aggregate
- `public/` — generated output directory (deployed to Pages)

### Data flow

1. Reads `repos.yaml` for repository list
2. Fetches `.agentready/assessment-latest.json` from each repo (GitLab API, GitHub API, or local filesystem)
3. Renders `public/index.html` via Jinja2 template

### Repository types

- `gitlab` — fetches via GitLab REST API (`GITLAB_TOKEN` or `CI_JOB_TOKEN`)
- `github` — fetches via GitHub REST API (`GITHUB_TOKEN`)
- `local` — reads directly from filesystem path

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Generate dashboard
python generate.py

# Generate from custom config
python generate.py path/to/repos.yaml

# View output
open public/index.html
```

## CI/CD

- GitHub Actions: `.github/workflows/pages.yml` — deploys to GitHub Pages on push to main, weekly schedule, manual dispatch
- GitLab CI: `.gitlab-ci.yml` — deploys to GitLab Pages on default branch push and scheduled pipelines
