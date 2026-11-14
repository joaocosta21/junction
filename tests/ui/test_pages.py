"""Every page answers in replay, says that the data is recorded and labels our own values as illustrative."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tta.ui import routes

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


def test_the_first_page_has_the_three_examples_the_demo_agents_and_a_run_button(client: TestClient) -> None:
    page = client.get("/").text

    assert "1,000 litres of lactose-free milk by Monday" in page
    assert "200 litres of a milk substitute by Monday; no milk, no gluten; confirmed data only" in page
    assert "473609" in page
    assert page.count('name="example"') == 3
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
