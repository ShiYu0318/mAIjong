"""Write NOTICE (SPEC appendix B.2): copyright, licences and third-party runtime dependencies.

Versions and licences come from the installed packages (Python: the backend and ai extras
plus the SDK's rl extra; frontend: package.json dependencies). Re-run after upgrading:

    uv run python scripts/generate_notice.py
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = """mAIjong
Copyright 2026-present ShiYu Huang (黃士育) and mAIjong contributors

The platform (engine, backend, AI training pipeline and frontend) is licensed under the
Apache License, Version 2.0 (see LICENSE). The sdk/ directory (maijong-sdk) is licensed
under the MIT License (see sdk/LICENSE).

This product includes the third-party software listed below, each under its own licence.
"""
FONTS = [
    ("Noto Sans TC", "SIL Open Font License 1.1", "loaded through Google Fonts"),
    ("LXGW WenKai TC", "SIL Open Font License 1.1", "loaded through Google Fonts"),
]
_NAME = re.compile(r"^[A-Za-z0-9_.\-]+")


def _python_requirements() -> list[str]:
    root = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    sdk = tomllib.loads((ROOT / "sdk" / "pyproject.toml").read_text())["project"]
    reqs = [r for extra in ("backend", "ai") for r in root["optional-dependencies"][extra]]
    reqs += sdk.get("optional-dependencies", {}).get("rl", [])
    names = {m.group(0).lower() for r in reqs if (m := _NAME.match(r))}
    return sorted(names)


def _python_license(name: str) -> tuple[str, str]:
    try:
        md = metadata.metadata(name)
    except metadata.PackageNotFoundError:
        return "not installed", "see the project"
    version = md.get("Version", "?")
    expr = md.get("License-Expression")
    if expr:
        return version, expr
    classifiers = [c.split(" :: ")[-1] for c in md.get_all("Classifier") or []
                   if c.startswith("License :: ")]
    if classifiers:
        return version, " / ".join(dict.fromkeys(classifiers))
    text = (md.get("License") or "").strip()
    if text and "\n" not in text and len(text) <= 60:
        return version, text
    return version, "see the project"


def _js_licenses() -> list[tuple[str, str, str]]:
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text())
    out = []
    for name in sorted(pkg.get("dependencies", {})):
        meta_path = ROOT / "frontend" / "node_modules" / name / "package.json"
        if not meta_path.exists():
            out.append((name, "not installed", "see the project"))
            continue
        meta = json.loads(meta_path.read_text())
        lic = meta.get("license")
        if isinstance(lic, dict):
            lic = lic.get("type")
        out.append((name, meta.get("version", "?"), lic or "see the project"))
    return out


def render() -> str:
    lines = [HEADER, "Python packages", "---------------"]
    for name in _python_requirements():
        version, lic = _python_license(name)
        lines.append(f"{name} {version}: {lic}")
    lines += ["", "JavaScript packages (frontend)", "------------------------------"]
    lines += [f"{name} {version}: {lic}" for name, version, lic in _js_licenses()]
    lines += ["", "Fonts", "-----"]
    lines += [f"{name}: {lic} ({how})" for name, lic, how in FONTS]
    return "\n".join(lines) + "\n"


def main() -> int:
    text = render()
    (ROOT / "NOTICE").write_text(text, encoding="utf-8")
    missing = [ln for ln in text.splitlines() if "not installed" in ln]
    print(f"NOTICE written ({len(text.splitlines())} lines)")
    for ln in missing:
        print(f"  warning: {ln}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
