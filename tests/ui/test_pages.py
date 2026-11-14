"""Every page answers in replay, says that the data is recorded and labels our own values as illustrative."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.ui import routes
from tta.ui.examples import EXAMPLES

Post = Callable[..., Any]


def test_each_page_answers_200_in_replay(client: TestClient, run_example: Post, only_order: Callable[..., Any]) -> None:
    run_example(client, "scenario-2")
    order_id = only_order(client, "agent:allergy-ward").order_id

    for path in ("/", "/approvals", "/assumptions", f"/orders/{order_id}", f"/orders/{order_id}?view=supplier"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.headers["content-type"].startswith("text/html")
    assert client.get("/static/app.css").headers["content-type"].startswith("text/css")
    assert "javascript" in client.get("/static/app.js").headers["content-type"]


def test_the_first_page_has_the_examples_the_demo_agents_and_a_run_button(client: TestClient) -> None:
    page = client.get("/").text

    assert "1,000 litres of lactose-free milk by Monday" in page
    assert "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only" in page
    assert "473609" in page
    assert "469512" in page  # the dietitian's example (task T18): an oat drink with no milk statement
    assert "most reliable delivery" in page  # the preference's example (task SUST-1): it changes the choice
    assert page.count('name="example"') == 6  # the bakery's waits for the bakery's demo agent
    assert "Hotel kitchen agent (demo)" in page and "Allergy ward agent (demo)" in page
    assert 'name="who"' in page and 'maxlength="2000"' in page
    assert ">Run<" in page


def test_the_profiles_are_shown_with_their_limits_and_labelled_as_illustrative(client: TestClient) -> None:
    page = client.get("/").text

    assert "€750" in page and "€500" in page  # what each agent may order alone
    assert "Illustrative" in page
    assert "The Valio Aimo mock has no customer limits" in page


def test_a_replay_label_is_visible_on_every_page(client: TestClient) -> None:
    for path in ("/", "/approvals", "/assumptions"):
        assert "Replay: recorded Valio Aimo data" in client.get(path).text


def test_a_result_says_which_recording_it_was_built_from(client: TestClient, run_example: Post) -> None:
    page = run_example(client, "scenario-2").text

    assert "recorded copy of Valio Aimo" in page
    assert "Saturday 14 Nov 2026 at 02:52" in page  # the capture's own clock


def test_an_unknown_page_is_a_404_page_that_does_not_repeat_the_path(client: TestClient) -> None:
    response = client.get("/no-such-page-made-up-by-the-caller")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "made-up-by-the-caller" not in response.text
    assert "Traceback" not in response.text


def test_the_api_keeps_its_own_paths_next_to_the_pages(client: TestClient) -> None:
    assert client.get("/healthz").json()["surfaces"]["pages"] is True
    missing = client.get("/v1/no-such-thing")
    assert missing.status_code == 404
    assert missing.headers["content-type"] == "application/problem+json"


def test_the_exact_path_v1_is_the_apis_and_not_a_page(client: TestClient) -> None:
    for path in ("/v1", "/v1/"):
        response = client.get(path)
        assert response.status_code == 404, path
        assert response.headers["content-type"] == "application/problem+json", path


def test_assumptions_renders_the_document_when_it_exists(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = tmp_path / "ASSUMPTIONS.md"
    document.write_text(
        "# Assumptions and next steps\n\nThe limit values are **ours**.\n\n- no order endpoint\n- <script>x</script>\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(routes, "ASSUMPTIONS_FILE", document)

    page = client.get("/assumptions").text

    assert "<h1>Assumptions and next steps</h1>" in page
    assert "<strong>ours</strong>" in page
    assert "<li>no order endpoint</li>" in page
    assert "<script>x</script>" not in page and "&lt;script&gt;x&lt;/script&gt;" in page


def test_assumptions_says_so_when_the_document_is_not_written_yet(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routes, "ASSUMPTIONS_FILE", tmp_path / "missing.md")

    response = client.get("/assumptions")

    assert response.status_code == 200
    assert "has not been written yet" in response.text
    assert str(tmp_path) not in response.text


def test_the_pages_need_the_demonstration_identities(client: TestClient) -> None:
    context = routes.SurfaceContext(
        settings=client.app.state.parts.settings, service=client.app.state.parts.service,  # type: ignore[attr-defined]
        identify=lambda token: None, demo_identities=(),
    )

    with pytest.raises(ValueError, match="demonstration identities"):
        routes.create_surface(context)


# --- one button per demo scenario, each with its customer (P2 W2, R9) -----------------------------------------

DEMO_ORDER = (  # PLAN section 5, then the reserve
    "1 · Harbourside Hotel", "2 · City Hospital, Ward 4", "3 · Harbourside Hotel", "4 · Harbourside Hotel",
    "Reserve · Harbourside Hotel",
)


def test_the_first_page_shows_the_demo_scenarios_in_demo_order_each_with_its_customer(client: TestClient) -> None:
    page = client.get("/").text
    start = page.index('class="examples"')
    examples = page[start:page.index("</form>", start)]

    places = [examples.index(heading) for heading in DEMO_ORDER]
    assert places == sorted(places)
    assert examples.count("Reserve · ") == 2
    assert 'href="/standing-orders"' in examples  # scenario 4 goes on there: the standing order at 290 L
    assert "ordered alone" not in examples.lower() and "orders alone" not in examples.lower()


def test_an_example_whose_customer_has_no_demo_agent_here_is_not_shown(
    client: TestClient, form_fields: Callable[..., Any]
) -> None:
    """The bakery's example (scenario 5) needs the bakery's demo agent, which another task adds."""
    bakery = next(example for example in EXAMPLES if example.key == "formula")
    page = client.get("/").text

    assert bakery.agent_id == "agent:bakery-cafe" and bakery.step == 5
    assert 'value="formula"' not in page and "Kallio Bakery" not in page
    refused = client.post("/run", data={**form_fields(client), "example": "formula"})
    assert refused.status_code == 422 and "No such example" in refused.text


def test_the_customers_pattern_asks_for_the_hotels_usual_100_litres(
    client: TestClient, run_example: Post, only_order: Callable[..., Any]
) -> None:
    """Measured at the recording's clock (Saturday 14 Nov 2026 02:52): 100 x 469363, €248.00, for a person."""
    page = run_example(client, "pattern").text
    order = only_order(client)

    assert [(line.product_id, line.quantity) for line in order.option.lines] == [("469363", 100)]
    assert order.option.totals.net == 248 and "Sent for approval" in page


@pytest.mark.parametrize("direction", ["demo order", "reversed"])
def test_the_examples_work_in_any_order_in_one_browser(
    client: TestClient, run_example: Post, orders: Callable[..., Any], direction: str
) -> None:
    """A4 H2: one pass over the examples stays under the hotel's €3,000 a day, so none asks finance (P-02)."""
    keys = ("scenario-1", "scenario-2", "scenario-3", "pattern", "scenario-5", "scenario-4")
    for key in keys if direction == "demo order" else reversed(keys):
        assert run_example(client, key).status_code == 200, key

    hotel = orders(client)
    assert len(hotel) == 5
    assert not any("P-02" in order.decision.rule_ids for order in hotel), [o.decision.rule_ids for o in hotel]
    assert sum(order.option.totals.net for order in hotel) < 3000


def test_every_old_page_links_to_the_shop(client: TestClient) -> None:
    """C2 section 8, #13: no way led from these pages to `/shop`. The link back is in the shop's own page."""
    for path in ("/", "/approvals", "/kitchen", "/menu", "/standing-orders", "/assumptions"):
        page = client.get(path).text
        nav = page[page.index('<nav aria-label="Pages">'):page.index("</nav>")]
        assert '<a href="/shop">' in nav, path
