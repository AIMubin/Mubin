"""Per-instance adapter capability registry. Never dispatch operations that are not declared."""
from __future__ import annotations
from .types import ContractError, ENGINE_NAMES, identifier


class EngineRegistry:
    def __init__(self):
        self._adapters = {}

    def register(self, engine, operations, handler):
        if engine not in ENGINE_NAMES or engine in self._adapters:
            raise ContractError("REGISTRY_ENGINE_INVALID")
        if (not isinstance(operations, (tuple, list, set, frozenset)) or not operations
                or not all(identifier(op) for op in operations) or not callable(handler)):
            raise ContractError("REGISTRY_CAPABILITIES_INVALID")
        self._adapters[engine] = (frozenset(operations), handler)

    def resolve(self, engine, operation):
        item = self._adapters.get(engine)
        if item is None:
            raise ContractError("ENGINE_UNAVAILABLE")
        ops, handler = item
        if operation not in ops:
            raise ContractError("OPERATION_UNSUPPORTED")
        return handler

    def capabilities(self):
        return {key: sorted(value[0]) for key, value in self._adapters.items()}
