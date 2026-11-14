"""
Keeps the documentation honest. Models and people follow the docs, so a doc that points at a file that is gone, or a
data model that is missing a field, sends them the wrong way. These fail when that happens.
"""
import pathlib
import re
import subprocess

import pytest

import untitledapp.shared as uas

ROOT = pathlib.Path(__file__).resolve().parent.parent

DOCS = sorted(
    [ROOT / "CLAUDE.md"]
    + [path for path in ROOT.glob("*/CLAUDE.md")]
    + list((ROOT / "docs").rglob("*.md"))
)

# [text](target): a relative link to another file in the repo.
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
# `api/untitledapp/occ.py`: a repo path in backticks, with an extension and no wildcard or placeholder.
CODE_PATH = re.compile(r"`((?:api|funcapp|src|tests|scripts|docs|adhoc|iac|\.github)/[\w./-]+\.\w+)`")


def _ids(paths):
    return [str(path.relative_to(ROOT)) for path in paths]


@pytest.mark.parametrize("doc", DOCS, ids=_ids(DOCS))
def test_links_point_at_files_that_exist(doc):
    missing = []
    for target in LINK.findall(doc.read_text(encoding="utf-8")):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue  # a web link or an anchor on the same page
        path = target.split("#")[0]
        if not (doc.parent / path).exists():
            missing.append(target)
    assert not missing, f"{doc.name} links to files that do not exist: {missing}"


def _git_ignored(path):
    """Local files such as ``funcapp/local.settings.json`` are named in the docs but never committed."""
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT, capture_output=True)
    return result.returncode == 0


@pytest.mark.parametrize("doc", DOCS, ids=_ids(DOCS))
def test_code_paths_exist(doc):
    missing = [
        path for path in CODE_PATH.findall(doc.read_text(encoding="utf-8"))
        if not (ROOT / path).exists() and not _git_ignored(path)
    ]
    assert not missing, f"{doc.name} names files that do not exist: {missing}"


def test_data_model_lists_every_kingdom_field():
    text = (ROOT / "docs" / "data-model.md").read_text(encoding="utf-8")
    missing = [field for field in uas.INITIAL_KINGDOM_STATE["kingdom"] if f"`{field}`" not in text]
    assert not missing, f"docs/data-model.md does not describe these kingdom fields: {missing}"


def test_data_model_lists_every_kingdom_document():
    text = (ROOT / "docs" / "data-model.md").read_text(encoding="utf-8")
    missing = [name for name in uas.INITIAL_KINGDOM_STATE if f"`{name}_<id>`" not in text]
    assert not missing, f"docs/data-model.md does not describe these per-kingdom documents: {missing}"
