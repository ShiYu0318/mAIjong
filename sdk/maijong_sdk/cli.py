"""maijong CLI: package, validate and submit agents (SPEC 06.3, 06.4).

maijong pack     --agent agent.py:MyAgent [--model model.pt] --name "MyBot v1"
maijong validate submission.zip
maijong submit   --agent agent.py:MyAgent [--model model.pt] --name "MyBot v1" \
                 --token $MAIJONG_API_TOKEN
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

from maijong_sdk import __version__

ALLOWED_REQUIREMENTS = ("torch", "numpy")


def pack(agent: str, model: Path | None, name: str, description: str,
         requirements: Path | None, out: Path) -> Path:
    path, _, cls = agent.partition(":")
    src = Path(path)
    if not src.exists() or not cls:
        raise SystemExit("--agent must look like path/to/agent.py:ClassName")
    manifest = {"agent_class": cls, "sdk_version": __version__, "name": name,
                "model_path": "model.pt" if model else None, "description": description}
    reqs = requirements.read_text() if requirements else ""
    for line in reqs.splitlines():
        pkg = line.split("=")[0].split("<")[0].split(">")[0].strip().lower()
        if pkg and not pkg.startswith("#") and pkg not in ALLOWED_REQUIREMENTS:
            raise SystemExit(f"requirement {pkg!r} is not allowed (only {ALLOWED_REQUIREMENTS})")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(src, "agent.py")
        if model:
            z.write(model, "model.pt")
        z.writestr("requirements.txt", reqs)
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return out


def validate(zip_path: Path, games: int = 10) -> dict[str, object]:
    from maijong_sdk.validation import validate_submission

    with tempfile.TemporaryDirectory() as d:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(d)
        return validate_submission(Path(d), games=games)


def submit(zip_path: Path, token: str, api: str) -> dict[str, object]:
    import urllib.request
    import uuid

    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"submission.zip\"\r\nContent-Type: application/zip\r\n\r\n").encode()
    body += zip_path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"{api.rstrip('/')}/api/v1/agents/submit", data=body, method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req) as resp:  # noqa: S310 - user-provided platform URL
        out: dict[str, object] = json.loads(resp.read())
        return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="maijong", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("pack", "submit"):
        p = sub.add_parser(name)
        p.add_argument("--agent", required=True)
        p.add_argument("--model", type=Path)
        p.add_argument("--name", required=True)
        p.add_argument("--description", default="")
        p.add_argument("--requirements", type=Path)
        p.add_argument("--out", type=Path, default=Path("submission.zip"))
        if name == "submit":
            p.add_argument("--token", default=os.environ.get("MAIJONG_API_TOKEN"))
            p.add_argument("--api", default=os.environ.get("MAIJONG_API_URL",
                                                           "http://localhost:8000"))
    v = sub.add_parser("validate")
    v.add_argument("zip", type=Path)
    v.add_argument("--games", type=int, default=10)
    args = ap.parse_args(argv)

    if args.cmd == "validate":
        report = validate(args.zip, args.games)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        sys.exit(0 if report["passed"] else 1)
    zip_path = pack(args.agent, args.model, args.name, args.description, args.requirements,
                    args.out)
    print(f"packaged {zip_path}")
    report = validate(zip_path)
    if not report["passed"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        raise SystemExit("local validation failed; fix the issues above before submitting")
    if args.cmd == "submit":
        if not args.token:
            raise SystemExit("--token or MAIJONG_API_TOKEN is required")
        print(json.dumps(submit(zip_path, args.token, args.api), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
