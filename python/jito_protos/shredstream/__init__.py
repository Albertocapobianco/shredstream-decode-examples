"""Convenience accessors for the generated shredstream protobuf modules."""

from __future__ import annotations

import importlib
from types import ModuleType

__all__ = ["shredstream_pb2", "shredstream_pb2_grpc"]


def _load(name: str) -> ModuleType:
    """Import a generated protobuf helper.

    The generated modules (``shredstream_pb2`` and ``shredstream_pb2_grpc``)
    are written into the top-level ``python/`` directory. When a user imports
    ``jito_protos.shredstream``, we eagerly pull those helpers in and expose
    them as attributes so existing ``from jito_protos.shredstream import …``
    statements keep working even though the compiled files are top-level
    modules. If the files are missing, we raise an informative error that
    points users towards the generation script.
    """

    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:  # pragma: no cover - passthrough guard
        raise ImportError(
            "Could not import the generated protobuf module "
            f"'{name}'. Did you run `python -m python.generate_protos`?"
        ) from exc


shredstream_pb2 = _load("shredstream_pb2")
shredstream_pb2_grpc = _load("shredstream_pb2_grpc")
