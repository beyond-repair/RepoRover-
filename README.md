<div align="center">

[![Lifecycle](https://img.shields.io/badge/●_ARCHIVE-64748b?style=for-the-badge&labelColor=0f0f23)](https://github.com/beyond-repair/ADL-Governance)
[![Claim](https://img.shields.io/badge/Claim_0-22c55e?style=for-the-badge&labelColor=0f0f23)](https://github.com/beyond-repair/ADL-Governance/blob/main/docs/CLAIM_VALIDATION.md)
[![Governance](https://img.shields.io/badge/ADL--Governance-7c3aed?style=for-the-badge&labelColor=0f0f23)](https://github.com/beyond-repair/ADL-Governance)

```
LIFECYCLE   ARCHIVE
CLAIM       0
NOT CLAIMED product · profit · deployment · portfolio intelligence
```

</div>

> **ARCHIVE QUEUE.** Historical GitHub README scraper sketch. Not a product. The abandoned v2 “portfolio intelligence” dashboard was **never implemented** and is **not** claimed here.

---

# RepoRover-

**Lifecycle:** ARCHIVED (Sweep-088) — runnable scraper sketch repaired for clean-clone verification.  
**Do not use as a dependency.** Do not treat as the account portfolio map.

## What this is

A small Python tool that:

1. Finds GitHub repositories (`--owner`, `--repos`, optional `--explore`, or offline `--demo`)
2. Fetches README markdown (GitHub API / `raw.githubusercontent.com`; fixtures in demo mode)
3. NLP-preprocesses (lowercase, strip HTML, tokenize, drop stopwords, stem or lemmatize)
4. Appends rows to a CSV (`Processed At`, `Repository Name`, `Homepage URL`, `Processed Readme.MD Content`)

It is **not** a portfolio-intelligence dashboard. For portfolio constitution / census / graph, use the canonical ADL repos below.

| Need | Canonical repo |
|------|----------------|
| Portfolio constitution / registry | [ADL-Governance](https://github.com/beyond-repair/ADL-Governance) |
| Locked inventory | [ADL-Portfolio-Census](https://github.com/beyond-repair/ADL-Portfolio-Census) |
| Capability matrix | [adl-capability-matrix](https://github.com/beyond-repair/adl-capability-matrix) |
| Repo graph | [aegis-repo-graph](https://github.com/beyond-repair/aegis-repo-graph) |

See `ARCHIVED.md` and `CLAIM_STATUS.md`.

## Requirements

- Python 3.10+
- Network only for live `--owner` / `--repos` / `--explore` (demo + tests are offline after NLTK data download)

## Installation

```bash
git clone https://github.com/beyond-repair/RepoRover-.git
cd RepoRover-
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

First run downloads NLTK `punkt`, `stopwords`, and `wordnet` into the local NLTK data path.

## Usage

### Offline demo (no GitHub network)

```bash
python -m RepoRover --demo
# CSV written to RepoRover/readmeMD.csv by default
```

### Explicit repos (API / raw README)

```bash
export GITHUB_TOKEN=...   # optional; raises API rate limits (gh auth token also works via GH_TOKEN)
python -m RepoRover --repos beyond-repair/RepoRover- pallets/flask --csv /tmp/readmes.csv
```

### List an owner’s public repos

```bash
python -m RepoRover --owner beyond-repair --max-repos 5
```

### Legacy Explore HTML (fragile; optional)

```bash
python -m RepoRover --explore
```

### Options

| Flag | Meaning |
|------|---------|
| `--demo` | Use bundled fixtures under `RepoRover/fixtures/` |
| `--stem` | Porter stemmer instead of WordNet lemmatizer |
| `--csv PATH` | Output CSV path |
| `--workers N` | Thread pool size for live fetches |

## Tests

```bash
pytest -q
```

Tests cover preprocess, CSV write/dedup, and the offline demo pipeline with fixtures/mocks (no live Explore HTML).

## Project layout

| Path | Role |
|------|------|
| `RepoRover/RepoRover.py` | Scraper pipeline + CLI |
| `RepoRover/fixtures/` | Offline demo READMEs + `repos.json` |
| `RepoRover/readmeMD.csv` | Default CSV (header stub in git) |
| `tests/test_reporover.py` | pytest suite |
| `requirements.txt` | pip deps (`requests`, `beautifulsoup4`, `nltk`, `pytest`) |

## Claims honesty

| Feature | State |
|---------|-------|
| README scrape + NLP + CSV (demo / API paths) | Verified by local pytest + demo run after this repair |
| Explore HTML scrape | Best-effort only; often broken on modern GitHub |
| v2 portfolio intelligence product | Never implemented; superseded by ADL-* repos |
| Product CI / releases | Absent |

---

<div align="center">

**REWRITE · BUILD · TRANSCEND**

Governing source: [ADL-Governance](https://github.com/beyond-repair/ADL-Governance) · [Claim levels 0–5](https://github.com/beyond-repair/ADL-Governance/blob/main/docs/CLAIM_VALIDATION.md)

</div>
