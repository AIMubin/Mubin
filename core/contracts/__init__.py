"""Versioned cross-engine contracts; not scholarly certification."""
from .types import CONTRACT_VERSION, ENGINE_NAMES, STATUSES, ContractError, validate_request
from .compatibility import validate_result
from .registry import EngineRegistry
