"""Tests for RepoRover scrape → preprocess → CSV pipeline (offline fixtures)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from RepoRover.RepoRover import (
    CSV_HEADERS,
    demo_fixture_loader,
    ensure_csv,
    ensure_nltk_data,
    load_demo_fixture_map,
    parse_repo_slug,
    preprocess_content,
    process_repository,
    run_pipeline,
)


@pytest.fixture(scope="module", autouse=True)
def _nltk():
    ensure_nltk_data()


def test_parse_repo_slug_url_and_short():
    assert parse_repo_slug("https://github.com/fixtures/sample-alpha") == (
        "fixtures",
        "sample-alpha",
    )
    assert parse_repo_slug("fixtures/sample-beta") == ("fixtures", "sample-beta")
    assert parse_repo_slug("not-a-repo") is None


def test_preprocess_stem_and_lemma():
    text = "<p>The Running dogs are jumping over fences quickly</p>"
    stemmed = preprocess_content(text, custom_processing=False)
    lemma = preprocess_content(text, custom_processing=True)
    assert "the" not in stemmed.split()
    assert "running" not in stemmed  # stemmed away
    assert "dog" in stemmed or "dogs" in stemmed or "dog" in lemma
    assert isinstance(lemma, str) and len(lemma) > 0
    # stopwords removed
    assert "are" not in lemma.split()


def test_demo_fixture_loader():
    content = demo_fixture_loader("https://github.com/fixtures/sample-alpha")
    assert content is not None
    assert "Sample Alpha" in content


def test_csv_write_and_dedup(tmp_path: Path):
    csv_path = tmp_path / "out.csv"
    ensure_csv(csv_path)
    names: set[str] = set()
    row = process_repository(
        "https://github.com/fixtures/sample-alpha",
        names,
        csv_file_path=csv_path,
        fixture_loader=demo_fixture_loader,
        use_lemma=True,
    )
    assert row is not None
    assert row["Repository Name"] == "fixtures/sample-alpha"
    assert len(row["Processed Readme.MD Content"]) > 0

    # duplicate skipped
    again = process_repository(
        "https://github.com/fixtures/sample-alpha",
        names,
        csv_file_path=csv_path,
        fixture_loader=demo_fixture_loader,
    )
    assert again is None

    with csv_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert list(rows[0].keys()) == CSV_HEADERS


def test_run_pipeline_demo(tmp_path: Path):
    csv_path = tmp_path / "demo.csv"
    entries = load_demo_fixture_map()
    urls = [e["html_url"] for e in entries]
    written = run_pipeline(
        urls,
        csv_file_path=csv_path,
        max_workers=1,
        fixture_loader=demo_fixture_loader,
        use_lemma=True,
    )
    assert written == 2
    with csv_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    names = {r["Repository Name"] for r in rows}
    assert names == {"fixtures/sample-alpha", "fixtures/sample-beta"}


def test_cli_demo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from RepoRover.RepoRover import main

    out = tmp_path / "cli.csv"
    rc = main(["--demo", "--csv", str(out), "--workers", "1"])
    assert rc == 0
    assert out.is_file()
    with out.open(encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == 2
