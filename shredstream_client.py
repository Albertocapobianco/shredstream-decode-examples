"""Asynchronous Python client for the Jito Shredstream proxy."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Iterable, Optional, Sequence, Set

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
from solders.entry import Entries  # noqa: E402  pylint: disable=wrong-import-position


KEEPALIVE_OPTIONS: Sequence[tuple[str, int]] = (
    ("grpc.keepalive_time_ms", 5_000),
    ("grpc.keepalive_timeout_ms", 10_000),
    ("grpc.http2.max_pings_without_data", 0),
    ("grpc.keepalive_permit_without_calls", 1),
    ("grpc.tcp_keepalive_time_ms", 15_000),
    ("grpc.client_idle_timeout_ms", 0),
)


async def stream_entries(
    endpoint: str,
    x_token: Optional[str],
    filter_accounts: Optional[Set[Pubkey]],
) -> None:
    """Connect to the shredstream proxy and print filtered transactions."""
    metadata: Sequence[tuple[str, str]] = (("x-token", x_token),) if x_token else ()

    async with aio.insecure_channel(endpoint, options=KEEPALIVE_OPTIONS) as channel:
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


def parse_pubkeys(values: Optional[Sequence[str]]) -> Optional[Set[Pubkey]]:
    if not values:
        return None

    parsed: Set[Pubkey] = set()
    for value in values:
        try:
            parsed.add(Pubkey.from_string(value))
        except ValueError as exc:
            raise SystemExit(f"Invalid pubkey provided: {value}") from exc
    return parsed


async def run_forever(args: argparse.Namespace) -> None:
    filter_accounts = parse_pubkeys(args.account_include)

    while True:
        try:
            await stream_entries(args.shredstream_uri, args.x_token, filter_accounts)
            logging.info("Stream ended gracefully. Reconnecting…")
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
