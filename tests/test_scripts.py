"""Deploy and log scripts, without a board."""

import os
import re
import subprocess
from pathlib import Path

import pytest

from bootstrap import find_brain_root

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "scripts" / "deploy_fly-memento.sh"
LOGS = ROOT / "scripts" / "logs_fly-memento.sh"


def _run(script: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
        env=env,
        cwd=ROOT,
    )


def _path_with_fake_ssh(tmp_path: Path) -> dict[str, str]:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for name in ("ssh", "scp"):
        program = bindir / name
        program.write_text("#!/bin/sh\necho ssh-called >&2\nexit 99\n", encoding="utf-8")
        program.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    return env


def test_find_brain_root_walks_to_the_checkout_and_to_a_vendored_copy(tmp_path):
    checkout = find_brain_root(ROOT / "robot" / "python" / "bootstrap.py")
    assert checkout == ROOT
    app = tmp_path / "ArduinoApps" / "fly-memento" / "python"
    package = app / "brain"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "brain.py").write_text("", encoding="utf-8")
    assert find_brain_root(app / "bootstrap.py") == app
    assert find_brain_root(tmp_path / "empty.py") is None


def test_deploy_dry_run_lists_the_app_and_does_not_ssh(tmp_path):
    done = _run(DEPLOY, "--dry-run", env=_path_with_fake_ssh(tmp_path))
    assert done.returncode == 0, done.stderr
    assert "ssh-called" not in done.stderr
    assert "archive robot ok" in done.stdout
    assert "archive brain ok: brain/ -> python/brain" in done.stdout
    assert "ArduinoApps/fly-memento" in done.stdout
    assert "memory dir kept: ~/fly-memento-data/memories" in done.stdout
    assert "arduino@uno-q-1.local" in done.stdout
    script = DEPLOY.read_text(encoding="utf-8")
    for line in script.splitlines():
        if "fly-memento-data" in line and "rm " in line:
            raise AssertionError(line)
    assert re.search(r"sketch hash [0-9a-f]{64}", done.stdout)
    again = _run(DEPLOY, "--dry-run", "--rebuild", "arduino@other.local", env=_path_with_fake_ssh(tmp_path))
    assert again.returncode == 0, again.stderr
    assert "arduino@other.local" in again.stdout
    assert "rebuild 1" in again.stdout
    assert re.search(r"sketch hash ([0-9a-f]{64})", done.stdout).group(1) == re.search(
        r"sketch hash ([0-9a-f]{64})", again.stdout
    ).group(1)


def test_logs_dry_run_names_a_timestamped_file_and_does_not_write_it(tmp_path):
    done = _run(LOGS, "--dry-run", "arduino@other.local", env=_path_with_fake_ssh(tmp_path))
    assert done.returncode == 0, done.stderr
    assert "ssh-called" not in done.stderr
    assert "arduino@other.local" in done.stdout
    assert "arduino-app-cli app logs ~/ArduinoApps/fly-memento --follow --tail 30" in done.stdout
    saved = next(line for line in done.stdout.splitlines() if line.startswith("save "))
    path = Path(saved.split(" ", 1)[1])
    assert path.parent == ROOT / "logs"
    assert re.fullmatch(r"fly-memento-\d{8}-\d{6}\.log", path.name)
    assert not path.exists()


@pytest.mark.parametrize("script", [DEPLOY, LOGS])
def test_unknown_option_exits_without_ssh(script, tmp_path):
    done = _run(script, "--not-a-flag", env=_path_with_fake_ssh(tmp_path))
    assert done.returncode == 2
    assert "unknown option: --not-a-flag" in done.stderr
    assert "ssh-called" not in done.stderr
