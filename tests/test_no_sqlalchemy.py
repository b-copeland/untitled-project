"""The web app does not need SQLAlchemy: nothing is stored in SQL any more (docs/decisions/0004-users-in-cosmos.md).

Runs in a fresh interpreter in which importing SQLAlchemy or Flask-SQLAlchemy raises, so the check holds even where
they are still installed.
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

SCRIPT = """
ROOT_API = %r
import sys
sys.path.insert(0, ROOT_API)

class Blocker:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0].lower() in ("sqlalchemy", "flask_sqlalchemy"):
            raise ImportError("blocked: " + name)

sys.meta_path.insert(0, Blocker())

import untitledapp
untitledapp.seed_testing_users = lambda: None  # needs the function app; this check is only about starting
app = untitledapp.create_app("config.TestingConfig")
assert app.url_map.iter_rules(), "no routes registered"
assert not any(m.split(".")[0].lower() in ("sqlalchemy", "flask_sqlalchemy") for m in sys.modules)
print("ok")
"""


def test_app_starts_without_sqlalchemy():
    result = subprocess.run(
        [sys.executable, "-I", "-c", SCRIPT % str(ROOT / "api")],
        cwd=ROOT / "api",
        env={"SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ok"


def test_requirements_do_not_list_sqlalchemy():
    for name in ("requirements.txt", "requirements-dev.txt"):
        text = (ROOT / name).read_text()
        assert not re.search(r"sqlalchemy", text, re.IGNORECASE), name
