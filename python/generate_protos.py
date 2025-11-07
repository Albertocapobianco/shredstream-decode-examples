"""Helper script to generate the Python protobuf stubs for the shredstream client."""
from __future__ import annotations

from pathlib import Path
import sys

from grpc_tools import protoc


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    proto_root = repo_root / "jito_protos" / "protos"
    output_dir = repo_root / "python"
    proto_file = proto_root / "shredstream" / "shredstream_proxy.proto"

    if not proto_file.exists():
        print(
            "Could not find the shredstream proto at"
            f" {proto_file}!\n"
            "Make sure the mev-protos submodule is present by running\n"
            "  git submodule update --init --recursive\n"
            "from the repository root. If you downloaded a ZIP archive,\n"
            "clone https://github.com/jito-labs/mev-protos and copy its\n"
            "contents into jito_protos/protos/.",
            file=sys.stderr,
        )
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
