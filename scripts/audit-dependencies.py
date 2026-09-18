"""Audit every locked package, mapping official local builds to their public release."""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from packaging.version import Version


def public_requirements(lock_text):
    requirements = []
    builds = []
    for raw_line in lock_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "--hash=", "--index-url ", "--extra-index-url ")):
            continue
        if not re.match(r"^[A-Za-z0-9_.-]+==[^\s;\\]+", line):
            raise ValueError("Lock contains an unpinned or unsupported dependency declaration")
    for name, raw_version in re.findall(r"^([A-Za-z0-9_.-]+)==([^\s;\\]+)", lock_text, re.M):
        version = Version(raw_version)
        if version.local:
            # This repository only uses the official PyTorch CPU build as a
            # non-PyPI variant. Never silently normalize arbitrary private forks.
            if name != "torch" or version.local != "cpu":
                raise ValueError(f"Unreviewed local build: {name}=={raw_version}")
            builds.append({"name": name, "build": raw_version, "audited_release": version.public})
        requirements.append(f"{name}=={version.public}")
    if not requirements:
        raise ValueError("No pinned dependencies found")
    return requirements, builds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    requirements, builds = public_requirements(args.lock.read_text(encoding="utf-8"))
    scratch = Path(__file__).resolve().parents[1] / "temp"
    scratch.mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".txt", dir=scratch, delete=False) as handle:
        handle.write("\n".join(requirements) + "\n")
        temporary = Path(handle.name)
    try:
        command = [
            sys.executable, "-m", "pip_audit", "-r", str(temporary), "--no-deps", "--disable-pip",
            "--format", "json", "--progress-spinner", "off", "--output", str(args.output),
        ]
        if args.cache_dir:
            command.extend(["--cache-dir", str(args.cache_dir)])
        result = subprocess.run(command, check=False)
        if result.returncode not in (0, 1):
            raise SystemExit(result.returncode)
        report = json.loads(args.output.read_text(encoding="utf-8"))
        report["source_lock"] = args.lock.as_posix()
        report["local_build_mappings"] = builds
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        skipped = [item for item in report["dependencies"] if item.get("skip_reason")]
        print(f"Checked {len(report['dependencies'])} packages; unresolved packages: {len(skipped)}")
        raise SystemExit(1 if skipped else result.returncode)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
