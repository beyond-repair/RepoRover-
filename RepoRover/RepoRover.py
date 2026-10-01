"""
RepoRover — GitHub README scraper sketch.

Pipeline (preserved identity):
  find repos → fetch README → NLP preprocess (tokenize/stopwords/stem-or-lemma) → append CSV

Prefer the GitHub REST API / raw.githubusercontent.com over brittle Explore HTML.
Offline --demo mode uses local fixtures so tests and clean-clone verify need no network.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import datetime
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.stem.porter import PorterStemmer
from nltk.tokenize import word_tokenize

PACKAGE_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = PACKAGE_DIR / "fixtures"
DEFAULT_CSV = PACKAGE_DIR / "readmeMD.csv"
CSV_HEADERS = [
    "Processed At",
    "Repository Name",
    "Homepage URL",
    "Processed Readme.MD Content",
]
GITHUB_API = "https://api.github.com"
RAW_GITHUB = "https://raw.githubusercontent.com"
DEFAULT_MAX_WORKERS = 4

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("reporover")

_nltk_ready = False


def ensure_nltk_data() -> None:
    """Download punkt + stopwords + wordnet once if missing (offline after first fetch)."""
    global _nltk_ready
    if _nltk_ready:
        return
    import nltk

    for resource, path in (
        ("punkt", "tokenizers/punkt"),
        ("punkt_tab", "tokenizers/punkt_tab"),
        ("stopwords", "corpora/stopwords"),
        ("wordnet", "corpora/wordnet"),
        ("omw-1.4", "corpora/omw-1.4"),
    ):
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(resource, quiet=True)
    _nltk_ready = True


def _auth_headers() -> dict[str, str]:
    token = (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_TOKEN")
        or os.environ.get("GH_PAT")
        or ""
    ).strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "RepoRover-scraper/0.1",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update(_auth_headers())
    return session


def parse_repo_slug(repo_url: str) -> Optional[tuple[str, str]]:
    """Extract (owner, repo) from a github.com URL or owner/repo slug."""
    text = repo_url.strip().rstrip("/")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text):
        owner, repo = text.split("/", 1)
        return owner, repo
    parsed = urlparse(text if "://" in text else f"https://{text}")
    if parsed.netloc not in {"github.com", "www.github.com"}:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    return parts[0], parts[1]


def list_repos_for_owner(
    owner: str,
    *,
    max_repos: int = 30,
    session: Optional[requests.Session] = None,
) -> list[str]:
    """List public repo HTML URLs for a user or org via the GitHub API."""
    sess = session or _session()
    urls: list[str] = []
    page = 1
    per_page = min(100, max_repos)
    while len(urls) < max_repos:
        # Try user endpoint first; fall back to org.
        for kind in ("users", "orgs"):
            api = f"{GITHUB_API}/{kind}/{owner}/repos"
            resp = sess.get(
                api,
                params={"per_page": per_page, "page": page, "type": "public", "sort": "updated"},
                timeout=30,
            )
            if resp.status_code == 404 and kind == "users":
                continue
            if resp.status_code == 403:
                logger.warning(
                    "GitHub API rate limited or forbidden for %s (status %s). "
                    "Set GITHUB_TOKEN or GH_TOKEN for higher limits.",
                    owner,
                    resp.status_code,
                )
                return urls
            if resp.status_code != 200:
                logger.warning("Failed to list repos for %s via %s: %s", owner, kind, resp.status_code)
                if kind == "users":
                    continue
                return urls
            batch = resp.json()
            if not isinstance(batch, list) or not batch:
                return urls
            for item in batch:
                html = item.get("html_url")
                if html:
                    urls.append(html)
                if len(urls) >= max_repos:
                    return urls
            if len(batch) < per_page:
                return urls
            page += 1
            break
        else:
            return urls
    return urls


def get_repo_urls_explore(
    page_url: str = "https://github.com/explore",
    *,
    session: Optional[requests.Session] = None,
) -> list[str]:
    """
    Best-effort Explore HTML scrape (legacy path). Modern GitHub markup often breaks this.
    Prefer --owner / --repos / --demo.
    """
    sess = session or _session()
    try:
        response = sess.get(page_url, timeout=30)
        if response.status_code != 200:
            logger.warning("Failed to fetch %s. Status code: %s", page_url, response.status_code)
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        hrefs: list[str] = []
        selectors = (
            "h1.h3.lh-condensed a[href]",
            "article h3 a[href]",
            "a[data-hydro-click*='Repository'][href]",
            "div.f4 a[href^='/']",
        )
        for sel in selectors:
            for link in soup.select(sel):
                href = link.get("href") or ""
                if href.count("/") >= 2 and not href.startswith("http"):
                    hrefs.append(f"https://github.com{href.split('?')[0]}")
                elif "github.com" in href:
                    hrefs.append(href.split("?")[0])
            if hrefs:
                break
        # Deduplicate while preserving order
        seen: set[str] = set()
        out: list[str] = []
        for u in hrefs:
            if u not in seen and parse_repo_slug(u):
                seen.add(u)
                out.append(u)
        return out
    except Exception as exc:  # noqa: BLE001 — scraper boundary
        logger.error("Error processing page %s: %s", page_url, exc)
        return []


def get_readme_content(
    repo_url: str,
    *,
    retries: int = 3,
    session: Optional[requests.Session] = None,
    fixture_loader: Optional[Callable[[str], Optional[str]]] = None,
) -> Optional[str]:
    """
    Retrieve README markdown for a repository.

    Order: optional fixture_loader → GitHub API readme → raw.githubusercontent.com defaults.
    """
    if fixture_loader is not None:
        content = fixture_loader(repo_url)
        if content is not None:
            return content

    slug = parse_repo_slug(repo_url)
    if not slug:
        logger.warning("Could not parse repo URL: %s", repo_url)
        return None
    owner, repo = slug
    sess = session or _session()

    # 1) GitHub Contents API (returns base64) — Accept raw for convenience
    api_url = f"{GITHUB_API}/repos/{owner}/{repo}/readme"
    for attempt in range(retries):
        try:
            resp = sess.get(
                api_url,
                headers={**sess.headers, "Accept": "application/vnd.github.raw"},
                timeout=30,
            )
            if resp.status_code == 200 and resp.text:
                return resp.text
            if resp.status_code == 404:
                break
            if resp.status_code in {403, 429} or resp.status_code >= 500:
                time.sleep(1 + attempt)
                continue
            break
        except requests.RequestException as exc:
            logger.error("Request error fetching README API for %s: %s", repo_url, exc)
            time.sleep(1 + attempt)

    # 2) raw.githubusercontent.com common default branches / filenames
    for branch in ("main", "master"):
        for name in ("README.md", "Readme.md", "readme.md", "README.MD"):
            raw_url = f"{RAW_GITHUB}/{owner}/{repo}/{branch}/{name}"
            try:
                resp = sess.get(raw_url, timeout=30)
                if resp.status_code == 200 and resp.text:
                    return resp.text
            except requests.RequestException as exc:
                logger.error("Request error fetching raw README %s: %s", raw_url, exc)
    logger.info("No README found for %s", repo_url)
    return None


def preprocess_content(content: str, custom_processing: bool = False) -> str:
    """
    Lowercase → strip HTML → tokenize → drop English stopwords → stem or lemmatize.
    custom_processing=True uses WordNet lemmatization; False uses Porter stemming.
    """
    ensure_nltk_data()
    preprocessed_content = content.lower()
    soup = BeautifulSoup(preprocessed_content, "html.parser")
    preprocessed_content = soup.get_text()
    tokens = word_tokenize(preprocessed_content)
    stop_words = set(stopwords.words("english"))
    filtered_tokens = [token for token in tokens if token not in stop_words and token.isalnum()]
    if custom_processing:
        lemmatizer = WordNetLemmatizer()
        processed_tokens = [lemmatizer.lemmatize(token) for token in filtered_tokens]
    else:
        stemmer = PorterStemmer()
        processed_tokens = [stemmer.stem(token) for token in filtered_tokens]
    return " ".join(processed_tokens)


def write_to_csv(data: dict[str, str], csv_file_path: Path | str) -> None:
    """Append one row to the CSV (caller ensures header exists)."""
    path = Path(csv_file_path)
    with path.open("a", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
        writer.writerow(data)


def ensure_csv(csv_file_path: Path | str) -> list[dict[str, str]]:
    """Create CSV with header if missing; return existing rows."""
    path = Path(csv_file_path)
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
            writer.writeheader()
        return []
    with path.open("r", encoding="utf-8") as csvfile:
        return list(csv.DictReader(csvfile))


def process_repository(
    repo_url: str,
    existing_names: set[str],
    *,
    csv_file_path: Path | str = DEFAULT_CSV,
    session: Optional[requests.Session] = None,
    fixture_loader: Optional[Callable[[str], Optional[str]]] = None,
    use_lemma: bool = True,
) -> Optional[dict[str, str]]:
    """Fetch README, preprocess, skip duplicates by repository name, append CSV."""
    readme_content = get_readme_content(
        repo_url, session=session, fixture_loader=fixture_loader
    )
    if not readme_content:
        return None

    slug = parse_repo_slug(repo_url)
    repo_name = f"{slug[0]}/{slug[1]}" if slug else repo_url.rstrip("/").split("/")[-1]

    if repo_name in existing_names:
        logger.info("Skipping duplicate repository: %s", repo_name)
        return None

    preprocessed_content = preprocess_content(readme_content, custom_processing=use_lemma)
    data = {
        "Processed At": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Repository Name": repo_name,
        "Homepage URL": repo_url if repo_url.startswith("http") else f"https://github.com/{repo_name}",
        "Processed Readme.MD Content": preprocessed_content,
    }
    write_to_csv(data, csv_file_path)
    existing_names.add(repo_name)
    logger.info("Processed repository: %s", repo_name)
    return data


def load_demo_fixture_map() -> dict[str, Any]:
    repos_path = FIXTURES_DIR / "repos.json"
    with repos_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def demo_fixture_loader(repo_url: str) -> Optional[str]:
    """Map demo repo URLs to local fixture markdown."""
    for entry in load_demo_fixture_map():
        if entry["html_url"].rstrip("/") == repo_url.rstrip("/") or entry["full_name"] in repo_url:
            path = FIXTURES_DIR / entry["readme_fixture"]
            return path.read_text(encoding="utf-8")
    return None


def run_pipeline(
    repo_urls: Iterable[str],
    *,
    csv_file_path: Path | str = DEFAULT_CSV,
    max_workers: int = DEFAULT_MAX_WORKERS,
    fixture_loader: Optional[Callable[[str], Optional[str]]] = None,
    use_lemma: bool = True,
) -> int:
    """Process URLs concurrently; return count of newly written rows."""
    existing = ensure_csv(csv_file_path)
    existing_names = {row.get("Repository Name", "") for row in existing}
    urls = list(repo_urls)
    if not urls:
        logger.info("No repository URLs to process.")
        return 0

    written = 0
    # Share one session only for sequential/demo; threads get their own via None default.
    # Fix: map must NOT zip existing_data as second positional arg.
    def _one(url: str) -> Optional[dict[str, str]]:
        return process_repository(
            url,
            existing_names,
            csv_file_path=csv_file_path,
            fixture_loader=fixture_loader,
            use_lemma=use_lemma,
        )

    if max_workers <= 1 or fixture_loader is not None:
        for url in urls:
            if _one(url):
                written += 1
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for result in executor.map(_one, urls):
                if result:
                    written += 1

    logger.info("Scouring completed. Wrote %s new row(s) to %s", written, csv_file_path)
    return written


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="RepoRover: scrape GitHub READMEs, preprocess with NLTK, append CSV."
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="Offline demo using bundled fixtures (no network).",
    )
    p.add_argument(
        "--owner",
        help="GitHub user or org whose public repos to list via API.",
    )
    p.add_argument(
        "--repos",
        nargs="+",
        help="Explicit repos as owner/name or https://github.com/owner/name URLs.",
    )
    p.add_argument(
        "--explore",
        action="store_true",
        help="Legacy best-effort scrape of github.com/explore (fragile; optional).",
    )
    p.add_argument(
        "--max-repos",
        type=int,
        default=10,
        help="Max repos when using --owner (default: 10).",
    )
    p.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help=f"Output CSV path (default: {DEFAULT_CSV})",
    )
    p.add_argument(
        "--stem",
        action="store_true",
        help="Use Porter stemming instead of lemmatization.",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Thread pool size for live fetches (default: 4).",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    ensure_nltk_data()

    fixture_loader = None
    repo_urls: list[str] = []

    if args.demo:
        entries = load_demo_fixture_map()
        repo_urls = [e["html_url"] for e in entries]
        fixture_loader = demo_fixture_loader
        logger.info("Demo mode: %s fixture repos", len(repo_urls))
    if args.repos:
        for item in args.repos:
            slug = parse_repo_slug(item)
            if not slug:
                logger.warning("Skipping unparseable repo: %s", item)
                continue
            repo_urls.append(f"https://github.com/{slug[0]}/{slug[1]}")
    if args.owner:
        repo_urls.extend(list_repos_for_owner(args.owner, max_repos=args.max_repos))
    if args.explore:
        repo_urls.extend(get_repo_urls_explore())

    # Deduplicate
    seen: set[str] = set()
    deduped: list[str] = []
    for u in repo_urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    if not deduped:
        logger.error(
            "No repositories selected. Use --demo, --owner NAME, --repos owner/name ..., "
            "or --explore."
        )
        return 2

    count = run_pipeline(
        deduped,
        csv_file_path=args.csv,
        max_workers=1 if fixture_loader else args.workers,
        fixture_loader=fixture_loader,
        use_lemma=not args.stem,
    )
    print(f"Processed {count} new repository row(s) → {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
