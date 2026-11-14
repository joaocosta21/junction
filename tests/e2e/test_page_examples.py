"""The examples of the first page are the demo set of docs/DEMO.md: same sentences, same order, and each sentence
is read by the gateway exactly as the typed request the example carries.

So a click on an example and the same sentence typed by hand give the same request, whoever reads it: with no
model key a sentence is answered from a labelled recording (scenarios 1 and 2) or read by the fixed rules.
Scores on the 30% end-to-end demo: every button of the first page runs, at both clocks.
"""

from __future__ import annotations

from typing import Any

from tta.contracts.request import PurchaseRequest
from tta.ui.examples import EXAMPLES

MAX_SENTENCES_TOGETHER = 600  # the demo's limit on request text (FX-S): the examples stay under it together
DEMO_SET = [  # (key, place in the demo set, customer): docs/DEMO.md; None is the reserve
    ("scenario-1", 1, "hotel"), ("scenario-2", 2, "ward"), ("scenario-3", 3, "hotel"), ("scenario-4", 4, "hotel"),
    ("almond", 4, "school"), ("pattern", 5, "hotel"), ("formula-changed", 6, "bakery"), ("formula", 6, "bakery"),
    ("scenario-5", None, "hotel"),
]
CUSTOMER = {
    "agent:hotel-kitchen": "hotel", "agent:allergy-ward": "ward", "agent:school-kitchen": "school",
    "agent:bakery-cafe": "bakery",
}


def test_the_examples_are_the_demo_set_in_its_order_each_with_its_customer(texts: Any) -> None:
    assert [(example.key, example.step, CUSTOMER[example.agent_id]) for example in EXAMPLES] == DEMO_SET
    by_key = {example.key: example.text for example in EXAMPLES}
    assert by_key["scenario-1"] == texts.scenario_1 and by_key["scenario-2"] == texts.scenario_2
    assert by_key["scenario-3"] == texts.scenario_3 and by_key["scenario-4"] == texts.dietitian
    assert by_key["almond"] == texts.almond and by_key["pattern"] == texts.pattern
    assert by_key["formula-changed"] == texts.formula_changed and by_key["formula"] == texts.formula_kept


def test_the_example_sentences_together_stay_under_the_demos_text_limit() -> None:
    assert sum(len(example.text) for example in EXAMPLES) < MAX_SENTENCES_TOGETHER


def test_each_example_sentence_is_read_exactly_as_its_typed_request_at_both_clocks(both: Any) -> None:
    differing = {}
    for example in EXAMPLES:
        read = PurchaseRequest.model_validate(both.parse(CUSTOMER[example.agent_id], example.text))
        if read != example.request:
            differing[example.key] = (read.model_dump(mode="json"), example.request.model_dump(mode="json"))

    assert differing == {}


def test_each_example_runs_from_its_sentence_to_an_order_that_waits_for_a_person(both: Any) -> None:
    for example in EXAMPLES:
        who = CUSTOMER[example.agent_id]
        run = both.run_agent(who, example.text)
        assert run["order_status"] == "PENDING_APPROVAL", (example.key, run["report"])
        offer = both.get_offer(who, run["offer_id"])
        assert PurchaseRequest.model_validate(offer["request"]) == example.request, example.key
        order = both.get_order(who, run["order_id"])
        assert order["placed_by"] is None and order["decision"]["required_roles"], example.key
