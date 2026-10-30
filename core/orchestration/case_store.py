"""Per-case snapshots only; no process-wide execution lock or false durable-store claim."""
from __future__ import annotations
from copy import deepcopy


class InMemoryCaseStore:
    def __init__(self):
        self._receipts = {}

    def save(self, case_id, receipt):
        self._receipts[case_id] = deepcopy(receipt)

    def get(self, case_id):
        return deepcopy(self._receipts.get(case_id))
