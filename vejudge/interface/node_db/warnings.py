"""Shared ``meta.warning`` text for a `node_db` node that matched/produced 0 items.

Per interface.md's "0-items warning" convention: matching nothing isn't necessarily wrong
(still reports ``status: "done"``), but a run that silently did nothing shouldn't look
identical to one that actually worked.
"""

from __future__ import annotations


def zero_items_warning(loader_kind: str) -> str:
    return (
        f"Matched 0 items for loader '{loader_kind}'. Check the project/use_case/item_id "
        "filters, and that VEJUDGE_REPO_ROOT (or VEJUDGE_DATA_ROOT/VEJUDGE_EVALUATION_ROOT) "
        "points at a real data checkout — a run can silently do nothing otherwise."
    )
