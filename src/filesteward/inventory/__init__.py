"""Streaming, read-only, fail-closed filesystem inventory."""

from filesteward.inventory.scan import ScanDeps, iter_inventory, stable_item_id

__all__ = ["ScanDeps", "iter_inventory", "stable_item_id"]
