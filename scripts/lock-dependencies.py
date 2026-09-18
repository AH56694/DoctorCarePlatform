"""Resolve Linux deployment dependencies, isolating PyTorch's CPU package index."""

import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    for source in ("requirements.txt", "python-service/requirements.txt"):
        output = str(Path(source).with_suffix(".lock"))
        subprocess.run([
            "uv", "pip", "compile", source,
            "--python-version", "3.11", "--python-platform", "x86_64-unknown-linux-gnu",
            "--torch-backend", "cpu", "--generate-hashes", "--emit-index-url",
            "--index-url", "https://pypi.org/simple", "--upgrade", "-q", "-o", output,
        ], cwd=root, check=True)
        path = root / output
        lock = path.read_text(encoding="utf-8")
        # Add the download location AFTER resolution. A global CPU resolver index
        # would select stale mirrored non-torch packages. pip uses the pinned hashes.
        lock = lock.replace(
            "--index-url https://pypi.org/simple\n",
            "--index-url https://pypi.org/simple\n"
            "--extra-index-url https://download.pytorch.org/whl/cpu\n", 1,
        )
        path.write_text(lock, encoding="utf-8")
        print(f"Locked {output}")


if __name__ == "__main__":
    main()
