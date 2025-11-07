"""Helper script to generate the Python protobuf stubs for the shredstream client."""
from __future__ import annotations

import sys
import textwrap
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

try:
    import grpc_tools
    from grpc_tools import protoc
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    raise SystemExit(
        "grpcio-tools is required to generate the protobuf bindings. "
        "Install it with `pip install grpcio-tools`."
    ) from exc


RAW_BASE_URL = "https://raw.githubusercontent.com/jito-labs/mev-protos/main"
REQUIRED_PROTOS: dict[Path, str] = {
    Path("shredstream.proto"): f"{RAW_BASE_URL}/protos/shredstream.proto",
    Path("shared.proto"): f"{RAW_BASE_URL}/protos/shared.proto",
}


def _download(url: str, destination: Path) -> bool:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec - trusted host
            data = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        print(
            textwrap.dedent(
                f"""
                Failed to download {url}: {exc}
                The repository already includes the required protobuf files under
                jito_protos/protos/. If you deleted them, restore the copies from git
                or manually fetch the latest versions from
                https://github.com/jito-labs/mev-protos.
                """
            ).strip(),
            file=sys.stderr,
        )
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    print(f"Saved {destination.name} to {destination}.")
    return True


def _ensure_protos(proto_root: Path) -> bool:
    missing: list[tuple[Path, str]] = []
    for relative_path, url in REQUIRED_PROTOS.items():
        target = proto_root / relative_path
        if target.exists():
            continue
        missing.append((target, url))

    if not missing:
        return True

    for target, url in missing:
        print(
            textwrap.dedent(
                f"""
                Could not find {target}.
                Attempting to download the file from {url} …
                """
            ).strip()
        )
        if not _download(url, target):
            return False

    return True


def _grpc_tools_include() -> Path:
    include_dir = Path(grpc_tools.__file__).resolve().parent / "_proto"
    if not include_dir.exists():
        raise FileNotFoundError(
            f"Could not locate the bundled google protobuf includes under {include_dir}."
        )
    return include_dir


def _build_args(
    include_paths: Iterable[Path], proto_files: Iterable[Path], output_dir: Path
) -> list[str]:
    args = ["grpc_tools.protoc"]
    for include in include_paths:
        args.append(f"-I{include}")

    args.extend(
        [
            f"--python_out={output_dir}",
            f"--grpc_python_out={output_dir}",
        ]
    )
    args.extend(str(path) for path in proto_files)
    return args


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    proto_root = repo_root / "jito_protos" / "protos"
    output_dir = repo_root / "python"
    proto_files = [proto_root / relative for relative in REQUIRED_PROTOS]

    if not _ensure_protos(proto_root):
        return 1

    include_paths = [proto_root, _grpc_tools_include()]
    args = _build_args(include_paths, proto_files, output_dir)
    return protoc.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
