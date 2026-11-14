"""A drop's reason in a few words (`tta.suggestions.reasons`) and Valio Aimo's own suggestion left silent
(`tta.suggestions.supplier.silenced`), on hand-built objects: no catalog, no recording."""

from __future__ import annotations

from decimal import Decimal

from tta.contracts.allergen import AllergenCheck, AllergenFinding
from tta.contracts.common import AllergenOutcome, AllergenRelation, ExclusionReason, Unit
from tta.contracts.suggestion import EvidenceSource, Serves, Suggestion, SuggestionEvidence, SuggestionKind
from tta.suggestions import DropReason
from tta.suggestions.reasons import ALLERGEN_DOUBT, allergen_summary, exclusion_summary
from tta.suggestions.supplier import Related, silenced

EVIDENCE = SuggestionEvidence(source=EvidenceSource.SUPPLIER, synthetic=True, orders_considered=8, orders_matching=0)


def _finding(code: str, outcome: AllergenOutcome, relation: AllergenRelation) -> AllergenFinding:
    return AllergenFinding(excluded_code=code, relation=relation, outcome=outcome, sentence=f"About {code}.")


def test_a_declared_allergen_is_named_before_one_the_data_leaves_open() -> None:
    check = AllergenCheck(outcome=AllergenOutcome.REJECT, all_explicit=False, findings=(
        _finding("AN", AllergenOutcome.TO_HUMAN, AllergenRelation.NOT_STATED),
        _finding("AM", AllergenOutcome.REJECT, AllergenRelation.CONTAINS),
        _finding("AY", AllergenOutcome.PASS, AllergenRelation.FREE_FROM),
    ))

    assert allergen_summary(check) == "it declares milk (AM)"
    assert exclusion_summary(ExclusionReason.ALLERGEN_DECLARED, check) == "it declares milk (AM)"


def test_an_allergen_doubt_without_findings_is_said_without_naming_one() -> None:
    passing = AllergenCheck(outcome=AllergenOutcome.PASS, all_explicit=True, findings=())

    assert allergen_summary(None) == allergen_summary(passing) == ALLERGEN_DOUBT


def test_the_offers_own_reasons_read_in_the_webshops_words() -> None:
    assert exclusion_summary(ExclusionReason.CUTOFF_PASSED, None) == "its closing time for ordering has passed"
    assert all(exclusion_summary(reason, None) for reason in ExclusionReason)


def test_a_bulk_product_for_a_usual_portion_pack_stays_silent_too() -> None:
    suggestion = Suggestion(
        suggestion_id="sug_from_supplier_463380_test", kind=SuggestionKind.FROM_SUPPLIER, serves=Serves.SUPPLIER,
        customer_id="test", product_id="463380", name="Arla Cafè milk 1 L UHT lactose free", quantity=Decimal(1),
        unit=Unit.UNIT, sentence="Valio Aimo suggests it.", evidence=EVIDENCE,
    )
    related = Related(suggestion=suggestion, anchor_id="463203", anchor_type="milk", portion_pack=False,
                      anchor_label="Arla Portion milk 100x2 cl lactose free 1,5% UHT (463203)", other_pack=True)

    silent = silenced(related, suggestion)

    assert silent is not None and silent.reason == DropReason.OTHER_PACK_KIND
    assert silent.sentence == (
        "Valio Aimo's own suggestion stays silent: Arla Cafè milk (463380) is not a portion pack, and the Arla "
        "Portion milk 100x2 cl lactose free 1,5% UHT (463203) you usually order is one."
    )
    assert silent.summary == "it is not a portion pack and your usual milk is one"
    assert silenced(related.__class__(suggestion=suggestion, anchor_id="463203"), suggestion) is None
