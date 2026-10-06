"""Regenerate two schema revisions separately with the pinned compiler."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    for version in ("v1", "v2"):
        output = ROOT / "generated" / version
        output.mkdir(parents=True, exist_ok=True)
        subprocess.run([
            sys.executable, "-m", "grpc_tools.protoc",
            f"-I{ROOT / 'schemas' / version}", f"--python_out={output}",
            str(ROOT / "schemas" / version / "envelope.proto"),
        ], check=True, timeout=20)


if __name__ == "__main__":
    main()
