"""scripts/refresh_loop.py: finding the secret, and surviving an API that is not there."""
import importlib.util
import pathlib

import pytest

spec = importlib.util.spec_from_file_location("refresh_loop", pathlib.Path(__file__).resolve().parent.parent / "scripts" / "refresh_loop.py")
refresh_loop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh_loop)


@pytest.fixture(autouse=True)
def setup():
    """Replaces the autouse fixture in conftest.py that sets up the backend: nothing here uses it."""
    yield


def test_the_secret_comes_from_the_environment_first_then_the_flaskenv_file(tmp_path):
    flaskenv = tmp_path / ".flaskenv"
    flaskenv.write_text("FLASK_APP=run\nREFRESH_SECRET='from-the-file'\nOTHER=1\n", encoding="utf-8")
    assert refresh_loop.read_secret(env={}, flaskenv=flaskenv) == "from-the-file"
    assert refresh_loop.read_secret(env={"REFRESH_SECRET": "from-env"}, flaskenv=flaskenv) == "from-env"


def test_no_secret_anywhere_is_none_not_a_crash(tmp_path):
    assert refresh_loop.read_secret(env={}, flaskenv=tmp_path / "missing") is None
    (tmp_path / "empty").write_text("REFRESH_SECRET=\n", encoding="utf-8")
    assert refresh_loop.read_secret(env={}, flaskenv=tmp_path / "empty") is None


def test_an_api_that_is_down_is_reported_not_raised():
    ok, text = refresh_loop.refresh_once("http://127.0.0.1:9", "secret", timeout=2)
    assert ok is False and "could not reach the API" in text


def test_the_secret_is_never_in_what_is_printed(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("REFRESH_SECRET", "hunter2-do-not-print")
    assert refresh_loop.main(["--once", "--url", "http://127.0.0.1:9"]) == 1
    output = capsys.readouterr()
    assert "hunter2" not in output.out + output.err and "FAILED" in output.out


def test_without_a_secret_it_says_so_and_stops(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("REFRESH_SECRET", raising=False)
    monkeypatch.setattr(refresh_loop, "FLASKENV", tmp_path / "none")
    monkeypatch.setattr(refresh_loop, "read_secret", lambda env=None, flaskenv=tmp_path / "none": None)
    assert refresh_loop.main(["--once"]) == 2
    assert "REFRESH_SECRET" in capsys.readouterr().err
