"""Learned brains on disk, outside the deployed app directory.

The directory is ``~/fly-memento-data/memories`` unless ``FLY_MEMENTO_DATA``
names a different parent. ``scripts/deploy_fly-memento.sh`` copies the app
to ``~/ArduinoApps/fly-memento`` and does not remove this tree, so a
redeploy leaves the files in place.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from brain.snapshot import SnapshotError, dump, load, parse

DATA_DIR_NAME = "fly-memento-data"
MEMORY_DIR_NAME = "memories"
_MAX_BYTES = 2_000_000


class StoreError(ValueError):
    """The name or the file on disk is not usable."""


def memory_dir() -> Path:
    override = os.environ.get("FLY_MEMENTO_DATA")
    root = Path(override).expanduser() if override else Path.home() / DATA_DIR_NAME
    path = root / MEMORY_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_name(name: str) -> str:
    text = str(name).strip()
    if not text:
        raise StoreError("名前が空です。")
    if len(text) > 80:
        raise StoreError("名前が長すぎます。")
    if text in {"upload", ".", ".."}:
        raise StoreError("その名前は使えません。")
    if any(char in text for char in "/\\\"\r\n\x00"):
        raise StoreError("名前に使えない文字があります。")
    if Path(text).name != text:
        raise StoreError("名前に使えない文字があります。")
    return text


def list_memories(directory: Path | None = None) -> list[dict]:
    folder = memory_dir() if directory is None else directory
    folder.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in folder.glob("*.json"):
        if not path.is_file():
            continue
        stat = path.stat()
        rows.append({"name": path.stem, "bytes": int(stat.st_size), "mtime": float(stat.st_mtime)})
    rows.sort(key=lambda row: row["mtime"], reverse=True)
    return rows


def save_memory(brain, name: str | None = None, directory: Path | None = None) -> dict:
    folder = memory_dir() if directory is None else directory
    folder.mkdir(parents=True, exist_ok=True)
    if name is None or not str(name).strip():
        name = time.strftime("%Y%m%d-%H%M%S")
    base = clean_name(name)
    chosen = base
    path = _file(folder, chosen)
    suffix = 2
    while path.exists():
        chosen = clean_name(f"{base}-{suffix}")
        path = _file(folder, chosen)
        suffix += 1
    payload = dump(brain)
    payload["name"] = chosen
    payload["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(f"memory save {path}", flush=True)
    return {"name": chosen, "path": str(path)}


def load_memory(brain, name: str, directory: Path | None = None) -> dict:
    path = _file(memory_dir() if directory is None else directory, clean_name(name))
    payload = _read(path)
    # Validate fully before the live brain changes.
    parse(payload, brain)
    load(brain, payload)
    print(f"memory load {path}", flush=True)
    return {"name": path.stem, "path": str(path)}


def import_memory(brain, raw: bytes, name: str | None = None, directory: Path | None = None) -> dict:
    """Validate an uploaded file, load it, and keep a copy in the memory dir."""
    if len(raw) > _MAX_BYTES:
        raise StoreError("ファイルが大きすぎます。")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StoreError("記憶ファイルが JSON ではありません。") from exc
    parse(payload, brain)
    load(brain, payload)
    chosen = name if name else payload.get("name")
    try:
        saved = save_memory(brain, name=None if chosen is None else str(chosen), directory=directory)
    except StoreError:
        saved = save_memory(brain, name=None, directory=directory)
    print(f"memory load {saved['path']}", flush=True)
    return saved


def delete_memory(name: str, directory: Path | None = None) -> dict:
    path = _file(memory_dir() if directory is None else directory, clean_name(name))
    if not path.is_file():
        raise StoreError("その記憶は見つかりません。")
    path.unlink()
    print(f"memory delete {path}", flush=True)
    return {"name": path.stem}


def read_memory(name: str, directory: Path | None = None) -> tuple[str, bytes]:
    path = _file(memory_dir() if directory is None else directory, clean_name(name))
    if not path.is_file():
        raise StoreError("その記憶は見つかりません。")
    return path.name, path.read_bytes()


def _file(folder: Path, name: str) -> Path:
    path = (folder / f"{name}.json").resolve()
    if path.parent != folder.resolve():
        raise StoreError("名前に使えない文字があります。")
    return path


def _read(path: Path) -> dict:
    if not path.is_file():
        raise StoreError("その記憶は見つかりません。")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StoreError("記憶ファイルが JSON ではありません。") from exc
    if not isinstance(payload, dict):
        raise SnapshotError("記憶ファイルがオブジェクトではありません。")
    return payload
