"""Helper script to generate the Python protobuf stubs for the shredstream client."""
from __future__ import annotations

import textwrap
import urllib.error
import urllib.request
from pathlib import Path
import sys

from grpc_tools import protoc


PROTO_URL = (
    "https://raw.githubusercontent.com/jito-labs/mev-protos/main/protos/shredstream.proto"
)


def _ensure_proto(proto_file: Path) -> bool:
    """Ensure that ``shredstream.proto`` is available locally.

    If the file is missing (common when the repository is downloaded as a ZIP without
    submodules), we attempt to download it from the upstream mev-protos repository.
    """

    if proto_file.exists():
        return True

    print(
        textwrap.dedent(
            f"""
            Could not find {proto_file}.
            Trying to download the file from {PROTO_URL} …
            """
        ).strip()
    )

    try:
        with urllib.request.urlopen(PROTO_URL, timeout=30) as response:  # nosec - trusted host
            proto_bytes = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        print(
            textwrap.dedent(
                f"""
                Failed to download shredstream.proto automatically: {exc}
                Please either initialise the mev-protos submodule with
                  git submodule update --init --recursive
                or copy the contents of https://github.com/jito-labs/mev-protos
                into jito_protos/protos/ manually.
                """
            ).strip(),
            file=sys.stderr,
        )
        return False

    proto_file.parent.mkdir(parents=True, exist_ok=True)
    proto_file.write_bytes(proto_bytes)
    print(f"Saved shredstream.proto to {proto_file}.")
    return True


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    proto_root = repo_root / "jito_protos" / "protos"
    output_dir = repo_root / "python"
    proto_file = proto_root / "shredstream.proto"

    if not _ensure_proto(proto_file):
        return 1

    args = [
        "grpc_tools.protoc",
        f"-I{proto_root}",
        f"--python_out={output_dir}",
        f"--grpc_python_out={output_dir}",
        str(proto_file),
    ]

    return protoc.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
