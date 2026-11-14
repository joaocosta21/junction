"""Web evidence for missing allergen data, through Context.dev (task S2, docs/CONTEXTDEV.md).

    finder = build_evidence_finder(settings, settings.tta_data_dir, catalog)  # None without a key
    orders = OrderBookService(..., evidence=finder)

The order book asks `finder.for_approval(option, decision)` before it writes an approval that P-04 created for an
allergen the product states nothing about; the approval carries the evidence, and the evidence changes nothing
else.
"""

from tta.evidence.finder import EvidenceFinder, build_evidence_finder, products_needing_evidence

__all__ = ["EvidenceFinder", "build_evidence_finder", "products_needing_evidence"]
