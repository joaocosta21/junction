"""AP-7: `deploy/evidence_batch.py`, with the Modal function called locally and a stand-in for Context.dev.
Nothing is sent to Modal or to Context.dev, and no test reads `.env`."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import modal
import pytest

import tta.config
from tta.catalog import ProductCatalog
from tta.config import REPO_ROOT, Settings
from tta.evidence import batch
from tta.evidence.answers import AnswerRecord, EvidenceUnavailable

KEY = "sentinel-context-key-not-a-real-one"
RETRIEVED_AT = datetime(2026, 11, 15, 7, 0, tzinfo=UTC)
NO_PAGE: dict[str, Any] = {
    "json_content": {"page_found": False, "source_url": None, "page_title": None, "product_name_on_page": None,
                     "contains": [], "may_contain": [], "free_from": []},
    "sources": [],
}
# Counted offline on the capture 2026-11-14-demo (769 products): those whose data holds no allergen statement.
SILENT_IN_THE_CAPTURE = 79


class StandIn:
    def __init__(self, refuse: frozenset[str] = frozenset()) -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []
        self.refuse, self.closed = refuse, 0

    def send(self, product_id: str, body: dict[str, Any]) -> AnswerRecord:
        self.sent.append((product_id, body))
        if product_id in self.refuse:
            raise EvidenceUnavailable("the research ran out of time")
        return AnswerRecord(product_id=product_id, retrieved_at=RETRIEVED_AT, request=body, body=NO_PAGE)

    def close(self) -> None:
        self.closed += 1


@pytest.fixture(scope="module")
def catalog() -> ProductCatalog:
    return ProductCatalog.from_settings(Settings.for_tests())


@pytest.fixture
def module(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    monkeypatch.setattr(tta.config, "get_settings", lambda: Settings.for_tests(context_dev_api_key=KEY))
    path = REPO_ROOT / "deploy" / "evidence_batch.py"
    spec = importlib.util.spec_from_file_location("tta_deploy_evidence_batch", path)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    sys.modules["tta_deploy_evidence_batch"] = loaded
    spec.loader.exec_module(loaded)
    yield loaded
    sys.modules.pop("tta_deploy_evidence_batch", None)


@pytest.fixture
def stand_in(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> StandIn:
    """Every call of the function builds its sender through `build_sender`: here, the stand-in."""
    sender = StandIn()
    monkeypatch.setattr(module, "build_sender", lambda: sender)
    return sender


def _locally(module: ModuleType) -> Any:
    """The fan-out without Modal: the same function, called in this process, one call after the other."""
    return lambda calls: [module.ask_page.local(call) for call in calls]


def _run(module: ModuleType, catalog: ProductCatalog, tmp_path: Path, **options: Any) -> tuple[int, list[str]]:
    lines: list[str] = []
    asked = module.run(
        out=lines.append, settings=Settings.for_tests(), catalog=catalog, directory=tmp_path / "evidence",
        **options,
    )
    return asked, lines


def test_a_dry_run_prints_the_count_and_the_cost_and_sends_nothing(
    module: ModuleType, catalog: ProductCatalog, tmp_path: Path, stand_in: StandIn
) -> None:
    def must_not_be_called(calls: Any) -> Any:
        raise AssertionError("a dry run asked for a page")

    asked, lines = _run(module, catalog, tmp_path, limit=200, dry_run=True, ask_all=must_not_be_called)

    assert (asked, stand_in.sent) == (0, [])
    assert lines == [
        f"{SILENT_IN_THE_CAPTURE} products of the capture 2026-11-14-demo hold no allergen statement; 0 of them "
        "already have a recorded page.",
        f"Dry run: {SILENT_IN_THE_CAPTURE} request(s) would be sent to Context.dev, at most 40 at a time, 100 "
        f"credits each, {SILENT_IN_THE_CAPTURE * 100} credits in all (limit 200). Nothing was sent.",
    ]
    assert not (tmp_path / "evidence").exists()


def test_the_limit_bounds_what_a_dry_run_would_send(
    module: ModuleType, catalog: ProductCatalog, tmp_path: Path
) -> None:
    _, lines = _run(module, catalog, tmp_path, limit=5, dry_run=True, ask_all=lambda calls: [])

    assert lines[-1].startswith("Dry run: 5 request(s) would be sent to Context.dev, at most 40 at a time, 100 credits "
                                "each, 500 credits in all (limit 5).")


def test_the_function_called_locally_sends_one_prepared_body_and_returns_the_answer(
    module: ModuleType, catalog: ProductCatalog, stand_in: StandIn
) -> None:
    call = batch.payload(catalog.get_product("464517"))

    result = module.ask_page.local(call)

    assert stand_in.sent == [("464517", call["request"])] and stand_in.closed == 1
    assert AnswerRecord.from_json(result).body == NO_PAGE
    assert set(call) == {"product_id", "request"}  # all a container receives: no buyer, no catalog
    assert KEY not in json.dumps(result) and KEY not in json.dumps(call)


def test_a_refusal_inside_a_call_comes_back_as_a_reason_and_never_as_an_error(
    module: ModuleType, catalog: ProductCatalog, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(module, "build_sender", lambda: StandIn(refuse=frozenset({"464517"})))

    result = module.ask_page.local(batch.payload(catalog.get_product("464517")))

    assert result == {"product_id": "464517", "unavailable": "the research ran out of time"}


def test_a_run_asks_at_most_the_limit_and_writes_each_answer_and_a_summary(
    module: ModuleType, catalog: ProductCatalog, tmp_path: Path, stand_in: StandIn
) -> None:
    asked, lines = _run(module, catalog, tmp_path, limit=3, dry_run=False, ask_all=_locally(module))

    assert asked == 3 and len(stand_in.sent) == 3
    assert len(list((tmp_path / "evidence").glob("*.json"))) == 3
    assert lines[1] == "Asking for 3 product(s), at most 40 at a time, 300 credits."
    assert "Products asked                                               3" in lines[2]
    assert "A page was found                                             0" in lines[2]
    assert lines[-1].endswith("Figures of this run only: a sample, not a catalog fact.")

    again, _ = _run(module, catalog, tmp_path, limit=3, dry_run=False, ask_all=_locally(module))
    assert again == 3 and len({product_id for product_id, _ in stand_in.sent}) == 6  # never the same product twice


def test_a_call_that_failed_on_modal_is_said_and_the_other_answers_are_kept(
    module: ModuleType, catalog: ProductCatalog, tmp_path: Path, stand_in: StandIn
) -> None:
    def one_fails(calls: Any) -> Any:
        return [TimeoutError("container"), *(module.ask_page.local(call) for call in calls[1:])]

    asked, lines = _run(module, catalog, tmp_path, limit=2, dry_run=False, ask_all=one_fails)

    assert asked == 2 and len(list((tmp_path / "evidence").glob("*.json"))) == 1
    assert "Answers received and stored                                  1" in lines[2]


def test_the_function_is_a_modal_function_capped_at_forty_and_never_retried(module: ModuleType) -> None:
    assert isinstance(module.ask_page, modal.Function)
    assert module.MAX_AT_ONCE == batch.MAX_AT_ONCE == 40
    assert module.NO_RETRIES == 0
    assert module.DEFAULT_LIMIT == 40


def test_the_secret_holds_the_context_dev_key_alone_and_nothing_inside_the_container(module: ModuleType) -> None:
    everything = Settings.for_tests(
        context_dev_api_key=KEY, valio_aimo_api_key="sentinel-valio", gemini_api_key="sentinel-gemini",
        database_url="sentinel-database-url",
    )

    def must_not_be_called() -> Settings:
        raise AssertionError("settings were read inside the container")

    assert module.secret_env(is_local=True, read_settings=lambda: everything) == {"CONTEXT_DEV_API_KEY": KEY}
    assert module.secret_env(is_local=True, read_settings=Settings.for_tests) == {}
    assert module.secret_env(is_local=False, read_settings=must_not_be_called) == {}
    assert KEY not in str(module.IMAGE_ENV)


def test_the_image_libraries_are_pinned_as_the_gateways(module: ModuleType, modal_app: ModuleType) -> None:
    assert set(module.PINNED) <= set(modal_app.PINNED)
    assert module.IMAGE_ENV["PYTHONPATH"] == f"{module.APP_ROOT}/src"


def test_the_file_claims_no_model_and_no_gpu(module: ModuleType) -> None:
    source = (REPO_ROOT / "deploy" / "evidence_batch.py").read_text(encoding="utf-8")

    assert "gpu=" not in source
    assert "It serves no model and uses no GPU" in module.__doc__
