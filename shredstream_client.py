"""Asynchronous Python client for the Jito Shredstream proxy."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

import importlib
import pkgutil

try:
    from importlib import metadata as importlib_metadata
except ImportError:  # pragma: no cover - Python <3.8
    import importlib_metadata  # type: ignore[no-redef]

import grpc
from grpc import aio


def _ensure_local_proto_path() -> None:
    """Add the local `python/` folder to ``sys.path`` if it exists.

    This allows the client to pick up generated protobuf modules without
    requiring them to be installed globally.
    """

    repo_python_dir = Path(__file__).resolve().parent / "python"
    if repo_python_dir.exists() and str(repo_python_dir) not in sys.path:
        sys.path.insert(0, str(repo_python_dir))


_ensure_local_proto_path()

try:  # noqa: E402  pylint: disable=wrong-import-position
    from jito_protos.shredstream import shredstream_pb2
    from jito_protos.shredstream import shredstream_pb2_grpc as shredstream_grpc
except ImportError as import_error:  # noqa: E402  pylint: disable=wrong-import-position
    try:
        from python import generate_protos
    except ImportError as helper_error:  # noqa: E402  pylint: disable=wrong-import-position
        raise ImportError(
            "Could not import the generated protobuf modules. "
            "Please run `python -m python.generate_protos` first."
        ) from helper_error

    exit_code = generate_protos.main()
    if exit_code != 0:
        raise ImportError(
            "Automatic protobuf generation failed. Check the logs above and "
            "ensure grpcio-tools is installed."
        ) from import_error

from jito_protos.shredstream import shredstream_pb2
from jito_protos.shredstream import shredstream_pb2_grpc as shredstream_grpc
from solders.pubkey import Pubkey  # noqa: E402  pylint: disable=wrong-import-position
from solders.transaction import VersionedTransaction  # noqa: E402  pylint: disable=wrong-import-position


class PythonEntry:
    """Lightweight container mirroring ``solders.ledger.entry.Entry``."""

    __slots__ = ("num_hashes", "hash", "transactions")

    def __init__(self, num_hashes: int, hash_bytes: bytes, transactions: Sequence[VersionedTransaction]):
        self.num_hashes = num_hashes
        self.hash = hash_bytes
        self.transactions = tuple(transactions)

    def __iter__(self) -> Iterator[VersionedTransaction]:
        return iter(self.transactions)


class PythonEntries(Sequence[PythonEntry]):
    """Pure Python fallback for decoding ledger entries."""

    __slots__ = ("_entries",)

    def __init__(self, entries: Sequence[PythonEntry]):
        self._entries = tuple(entries)

    @classmethod
    def from_bytes(cls, data: bytes) -> "PythonEntries":
        buffer = memoryview(data)
        offset = 0

        total, offset = _read_varint(buffer, offset)
        entries: List[PythonEntry] = []

        for _ in range(total):
            num_hashes, offset = _read_u64(buffer, offset)
            hash_bytes, offset = _read_bytes(buffer, offset, 32)
            tx_count, offset = _read_varint(buffer, offset)

            transactions: List[VersionedTransaction] = []
            for _ in range(tx_count):
                length, offset = _read_varint(buffer, offset)
                tx_bytes, offset = _read_bytes(buffer, offset, length)
                transactions.append(VersionedTransaction.from_bytes(bytes(tx_bytes)))

            entries.append(PythonEntry(num_hashes, bytes(hash_bytes), transactions))

        if offset != len(buffer):
            raise ValueError("Unexpected trailing bytes when decoding ledger entries")

        return cls(entries)

    def __iter__(self) -> Iterator[PythonEntry]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __getitem__(self, index: int) -> PythonEntry:
        return self._entries[index]


Entries = None


def _read_varint(buffer: memoryview, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0

    while True:
        if offset >= len(buffer):
            raise ValueError("Unexpected end of buffer while decoding varint")

        byte = buffer[offset]
        offset += 1
        value |= (byte & 0x7F) << shift

        if byte & 0x80 == 0:
            break

        shift += 7
        if shift >= 64:
            raise ValueError("Varint is too long")

    return value, offset


def _read_u64(buffer: memoryview, offset: int) -> tuple[int, int]:
    return int.from_bytes(_slice_bytes(buffer, offset, 8), "little"), offset + 8


def _read_bytes(buffer: memoryview, offset: int, length: int) -> tuple[memoryview, int]:
    return _slice_bytes(buffer, offset, length), offset + length


def _slice_bytes(buffer: memoryview, offset: int, length: int) -> memoryview:
    end = offset + length
    if end > len(buffer):
        raise ValueError("Unexpected end of buffer while decoding bytes")
    return buffer[offset:end]


def _import_entries_from(module_name: str) -> Optional[type]:
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        return None

    return getattr(module, "Entries", None)


def _discover_solders_modules() -> Set[str]:  # pragma: no cover - import side effect wrapper
    modules: Set[str] = set()

    try:
        import solders  # type: ignore import-not-found
    except ModuleNotFoundError as exc:
        raise ImportError("The `solders` package is not installed.") from exc

    solders_path = getattr(solders, "__path__", ())
    modules.update(
        module_info.name
        for module_info in pkgutil.walk_packages(solders_path, prefix="solders.")
        if "ledger" in module_info.name or module_info.name.endswith(("entry", "entries"))
    )

    try:
        files = importlib_metadata.files("solders")
    except Exception:  # pragma: no cover - metadata lookup is best effort
        files = None

    if files is not None:
        for file in files:
            suffix = file.suffix
            if suffix not in {".py", ".pyi", ".so", ".pyd"}:
                continue

            stem = file.with_suffix("")
            parts = [part for part in stem.parts if part not in {"__pycache__"}]
            if not parts or parts[0] != "solders":
                continue

            module_name = ".".join(parts)
            if "ledger" in module_name or module_name.endswith(("entry", "entries")):
                modules.add(module_name)

    return modules


def _load_entries_type() -> type:  # pragma: no cover - import side effect wrapper
    """Load the ``Entries`` helper from the installed ``solders`` wheel."""

    candidate_modules = {
        "solders.entry",
        "solders.entry.entry",
        "solders.ledger.entry",
        "solders.ledger.entries",
        "solders.ledger.entry_pb2",
    }

    try:
        candidate_modules.update(_discover_solders_modules())
    except ImportError:
        raise
    except Exception:  # pragma: no cover - discovery is best effort
        pass

    for module_name in sorted(candidate_modules):
        entries_type = _import_entries_from(module_name)
        if entries_type is not None:
            logging.debug("Loaded Entries helper from %s", module_name)
            return entries_type

    raise ImportError("The installed `solders` wheel does not expose the `Entries` helper.")


try:
    Entries = _load_entries_type()
except ImportError:
    logging.getLogger(__name__).warning(
        "Falling back to the built-in Python ledger decoder because the installed "
        "`solders` wheel lacks ledger bindings. Install `solders[ledger]` for the "
        "native implementation."
    )
    Entries = PythonEntries


KEEPALIVE_OPTIONS: Sequence[tuple[str, int]] = (
    ("grpc.keepalive_time_ms", 5_000),
    ("grpc.keepalive_timeout_ms", 10_000),
    ("grpc.http2.max_pings_without_data", 0),
    ("grpc.keepalive_permit_without_calls", 1),
    ("grpc.tcp_keepalive_time_ms", 15_000),
    ("grpc.client_idle_timeout_ms", 0),
)


def _normalize_endpoint(raw_endpoint: str) -> Tuple[str, Optional[grpc.ChannelCredentials]]:
    """Return a gRPC target string and optional credentials from a URI."""

    if "://" not in raw_endpoint:
        return raw_endpoint, None

    parsed = urlparse(raw_endpoint)

    if not parsed.hostname:
        raise ValueError(
            "L'URI fornito non contiene un host valido. Esempio: https://example.com:443"
        )

    if parsed.scheme not in {"http", "https"}:
        raise ValueError(
            "Schema URI non supportato. Usa http:// o https:// oppure specifica direttamente host:porta."
        )

    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80

    target = f"{parsed.hostname}:{port}"

    if parsed.scheme == "https":
        return target, grpc.ssl_channel_credentials()

    return target, None


async def stream_entries(
    endpoint: str,
    x_token: Optional[str],
    filter_accounts: Optional[Set[Pubkey]],
) -> None:
    """Connect to the shredstream proxy and print filtered transactions."""
    metadata: Sequence[tuple[str, str]] = (("x-token", x_token),) if x_token else ()

    target, credentials = _normalize_endpoint(endpoint)

    channel_factory = (
        aio.secure_channel if credentials is not None else aio.insecure_channel
    )

    channel_kwargs = {"options": KEEPALIVE_OPTIONS}
    if credentials is not None:
        channel_kwargs["credentials"] = credentials

    async with channel_factory(target, **channel_kwargs) as channel:
        client = shredstream_grpc.ShredstreamProxyStub(channel)
        request = shredstream_pb2.SubscribeEntriesRequest()

        stream = client.SubscribeEntries(request, metadata=metadata)

        async for slot_entry in stream:
            try:
                entries = Entries.from_bytes(slot_entry.entries)
            except Exception as exc:  # pylint: disable=broad-except
                logging.exception("Failed to decode entries from slot %s: %s", slot_entry.slot, exc)
                continue

            for entry in entries:
                for transaction in entry.transactions:
                    if _should_print_transaction(transaction, filter_accounts):
                        print(f"Transaction: {transaction}\n")


def _should_print_transaction(transaction, filter_accounts: Optional[Set[Pubkey]]) -> bool:
    if not filter_accounts:
        return True

    message = transaction.message
    try:
        account_keys: Iterable[Pubkey] = message.static_account_keys()
    except AttributeError:
        # Older versions of solders expose `account_keys` instead of `static_account_keys`.
        account_keys = message.account_keys

    return any(key in filter_accounts for key in account_keys)


BASE58_ALPHABET = frozenset("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")


def _pubkey_error_hint(raw_value: str) -> str:
    """Return a human-friendly hint when a pubkey fails to parse."""

    hints: List[str] = []
    stripped = raw_value.strip()

    if stripped != raw_value:
        hints.append("La chiave contiene spazi iniziali o finali: riprova senza spazi.")

    length = len(stripped)
    if length < 43:
        hints.append(
            "La chiave sembra troppo corta (circa 43-44 caratteri attesi per una chiave base58 valida). "
            "Assicurati di averla copiata per intero."
        )
    elif length > 44:
        hints.append(
            "La chiave sembra troppo lunga: controlla di non aver aggiunto caratteri extra."
        )

    invalid_chars = sorted({char for char in stripped if char not in BASE58_ALPHABET})
    if invalid_chars:
        hints.append(
            "Sono stati trovati caratteri non validi (solo base58 è ammesso): "
            + "".join(invalid_chars)
            + "."
        )

    return " ".join(hints)


def parse_pubkeys(values: Optional[Sequence[str]]) -> Optional[Set[Pubkey]]:
    if not values:
        return None

    parsed: Set[Pubkey] = set()
    for value in values:
        try:
            parsed.add(Pubkey.from_string(value))
        except ValueError as exc:
            hint = _pubkey_error_hint(value)
            message = f"Invalid pubkey provided: {value}."
            if hint:
                message += f" {hint}"
            raise SystemExit(message) from exc
    return parsed


async def run_forever(args: argparse.Namespace) -> None:
    filter_accounts = parse_pubkeys(args.account_include)

    while True:
        try:
            await stream_entries(args.shredstream_uri, args.x_token, filter_accounts)
            logging.info("Stream ended gracefully. Reconnecting…")
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        except grpc.RpcError as exc:
            logging.error("Connection or stream error: %s. Retrying…", exc)

        await asyncio.sleep(1)


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="Stream transactions from a Jito shredstream proxy")
    parser.add_argument(
        "--shredstream-uri",
        "-s",
        default="http://127.0.0.1:9999",
        help="Address of the shredstream proxy",
    )
    parser.add_argument("--x-token", "-x", help="Authentication token for the proxy", default=None)
    parser.add_argument(
        "--account-include",
        "-a",
        nargs="+",
        help="Filter transactions to only those touching the provided accounts",
    )

    args = parser.parse_args()

    if "RUST_LOG" not in os.environ:
        os.environ["RUST_LOG"] = "info"

    asyncio.run(run_forever(args))


if __name__ == "__main__":
    main()
