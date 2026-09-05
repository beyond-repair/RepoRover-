# RepoRover — GitHub Portfolio Intelligence

**Status:** Resurrection target (v1 scraper → v2 intelligence)  
**Lab:** [Atomic Dream Labs / beyond-repair](https://github.com/beyond-repair)  
**License:** MIT (see LICENSE if present)

---

## Purpose

RepoRover turns a GitHub account or organization into a **readable intelligence surface**: what exists, what claims it makes, how healthy documentation is, and how repositories relate.

Legacy code in this repository scraped README content into CSV. That remains a useful data path. The **strategic product** is broader:

```
GitHub repos
    → harvest (README, metadata, structure signals)
    → normalize
    → join with ADL census / capability matrix / repo graph
    → health, debt, claim, and architecture views
```

---

## Why this is undervalued

Most developers have many repositories and no portfolio map. This lab already maintains:

- [ADL-Portfolio-Census](https://github.com/beyond-repair/ADL-Portfolio-Census)
- [adl-capability-matrix](https://github.com/beyond-repair/adl-capability-matrix)
- [aegis-repo-graph](https://github.com/beyond-repair/aegis-repo-graph)
- [ADL-Governance](https://github.com/beyond-repair/ADL-Governance)

RepoRover is the **operator-facing layer** over those systems — not a duplicate census.

---

## Features

### Current (legacy v1)

- Fetch README content from GitHub repositories
- Basic text normalization (case, tags, tokenization)
- Duplicate checks
- CSV export for offline analysis

### Target (v2)

| Capability | Description |
|------------|-------------|
| Repo health | Docs present, last push age, empty README detection |
| Claim surface | Align descriptions with governance claim caps |
| Dependency / relation graph | Consume or mirror aegis-repo-graph |
| Technical debt signals | Stub density, missing tests, abandoned forks |
| Architecture maps | Cluster by pillar (mind, physics, games, governance) |

---

## Quick start (legacy)

```bash
# Install dependencies (see requirements.txt if present)
pip install -r requirements.txt

# Example invocation — adjust to actual entrypoint in tree
python RepoRover.py
```

Output: processed repository documentation data (historically `readmeMD.csv`).

---

## Scope (claim-capped)

**Does claim**

- Assistance for portfolio visibility and documentation analysis  
- Integration path with ADL governance artifacts  

**Does not claim**

- Full static analysis of every language  
- Automatic legal compliance certification  
- Replacement for GitHub Advanced Security products  

---

## Roadmap

1. Stabilize harvest CLI and schema  
2. Emit JSON as well as CSV  
3. Join fields with portfolio census IDs  
4. Optional local dashboard (read-only)  

---

## Related repositories

| Repo | Role |
|------|------|
| ADL-Portfolio-Census | Locked inventory |
| aegis-repo-graph | Typed repo relationships |
| adl-capability-matrix | Compatible-build queue |
| DevelopTool-Unified-Dev-Environment | Agent engineering UX thesis |

---

*Atomic Dream Labs — see the portfolio, not only the files*
