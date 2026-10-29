"""Bounded DAG plans. A semantic model may PROPOSE a plan, but this validator accepts it."""
from __future__ import annotations
from dataclasses import dataclass
import json
from core.contracts.types import ContractError, ENGINE_NAMES, identifier


class PlanError(ValueError):
    """Safe machine-readable plan rejection."""


@dataclass(frozen=True)
class CasePlan:
    case_id: str
    methodology_profile_id: str
    source_snapshot_ids: tuple[str, ...]
    nodes: tuple[dict, ...]
    max_parallel: int = 4

    def ordered(self):
        if not identifier(self.case_id) or not identifier(self.methodology_profile_id):
            raise PlanError("PLAN_IDENTIFIERS_INVALID")
        if (not isinstance(self.source_snapshot_ids, tuple)
                or len(self.source_snapshot_ids) > 128
                or len(set(self.source_snapshot_ids)) != len(self.source_snapshot_ids)
                or not all(identifier(x) for x in self.source_snapshot_ids)):
            raise PlanError("PLAN_SNAPSHOTS_INVALID")
        if type(self.max_parallel) is not int or not 1 <= self.max_parallel <= 16:
            raise PlanError("PLAN_PARALLELISM_INVALID")
        if not isinstance(self.nodes, tuple) or not 1 <= len(self.nodes) <= 64:
            raise PlanError("PLAN_NODE_COUNT_INVALID")
        nodes = {}
        keys = set()
        for node in self.nodes:
            if type(node) is not dict or set(node) != {"id", "engine", "operation", "inputs", "depends_on", "timeout_ms", "max_results"}:
                raise PlanError("PLAN_NODE_SHAPE_INVALID")
            if (not identifier(node["id"]) or node["id"] in nodes
                    or node["engine"] not in ENGINE_NAMES or not identifier(node["operation"])):
                raise PlanError("PLAN_NODE_IDENTITY_INVALID")
            if type(node["inputs"]) is not dict:
                raise PlanError("PLAN_NODE_LIMITS_INVALID")
            try:
                canonical_inputs = json.dumps(node["inputs"], sort_keys=True, allow_nan=False,
                                             ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError, RecursionError) as exc:
                raise PlanError("PLAN_INPUT_NOT_JSON") from exc
            if (len(canonical_inputs.encode("utf-8")) > 65536
                    or type(node["timeout_ms"]) is not int or not 1 <= node["timeout_ms"] <= 120000
                    or type(node["max_results"]) is not int or not 1 <= node["max_results"] <= 1000):
                raise PlanError("PLAN_NODE_LIMITS_INVALID")
            deps = node["depends_on"]
            if (type(deps) is not list or len(deps) > 64 or len(set(deps)) != len(deps)
                    or not all(identifier(d) for d in deps)):
                raise PlanError("PLAN_DEPENDENCIES_INVALID")
            key = (node["engine"], node["operation"], canonical_inputs)
            if key in keys:
                raise PlanError("PLAN_DUPLICATE_OPERATION")
            keys.add(key)
            nodes[node["id"]] = node
        if any(dep not in nodes for node in nodes.values() for dep in node["depends_on"]):
            raise PlanError("PLAN_MISSING_DEPENDENCY")
        visiting, visited, ordered = set(), set(), []
        def visit(n):
            if n in visiting:
                raise PlanError("PLAN_CYCLE")
            if n in visited:
                return
            visiting.add(n)
            for dep in nodes[n]["depends_on"]:
                visit(dep)
            visiting.remove(n)
            visited.add(n)
            ordered.append(nodes[n])
        for name in nodes:
            visit(name)
        return ordered
