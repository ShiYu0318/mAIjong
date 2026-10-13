"""SPEC appendix B: licence files, declarations and an up-to-date NOTICE."""

from __future__ import annotations

import importlib.util
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_license_files_and_declarations():
    assert "Apache License" in (ROOT / "LICENSE").read_text()
    assert (ROOT / "sdk" / "LICENSE").read_text().startswith("MIT License")
    root = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    sdk = tomllib.loads((ROOT / "sdk" / "pyproject.toml").read_text())["project"]
    assert root["license"] == {"text": "Apache-2.0"}
    assert sdk["license"] == {"text": "MIT"}
    assert "License :: OSI Approved :: MIT License" in sdk["classifiers"]
    assert json.loads((ROOT / "frontend" / "package.json").read_text())["license"] == "Apache-2.0"


def test_notice_lists_every_runtime_dependency():
    spec = importlib.util.spec_from_file_location("generate_notice",
                                                  ROOT / "scripts" / "generate_notice.py")
    assert spec and spec.loader
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    notice = (ROOT / "NOTICE").read_text()
    assert "Copyright 2026-present ShiYu Huang" in notice
    listed = {line.split(" ")[0] for line in notice.splitlines() if ": " in line}
    missing = [n for n in gen._python_requirements() if n not in listed]
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text())
    missing += [n for n in pkg["dependencies"] if n not in listed]
    assert not missing, f"re-run scripts/generate_notice.py; NOTICE lacks {missing}"
