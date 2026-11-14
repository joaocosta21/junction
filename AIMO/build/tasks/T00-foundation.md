# T00 — Foundation (done by the orchestrator, before any agent starts)

**Scores on:** everything; nothing can start without it.
**Needs:** the human's start command (it carries the authorisations listed in `RUNBOOK.md`).

## Steps
1. **Branch.** `git fetch origin`; `git switch -c overnight-build` (the uncommitted document changes come along); commit them as `docs: reframe plan, add build spec and overnight tasks`; merge `origin/bio1` and `origin/bio2` (both only add files). No push. No AI trailer in any commit message.
2. **Ignore rules.** Add to `.gitignore`: `.venv/`, `__pycache__/`, `.pytest_cache/`, `.coverage`, `var/`, `.claude/settings.local.json`.
3. **Environment.** `python3 -m venv .venv`; `pyproject.toml` (package `tta` in `src/`, Python ≥ 3.13) declaring: `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `httpx`, `pyyaml`, `jinja2`, `python-multipart`, `google-genai`, `mcp`, `modal`, and for development `pytest`, `pytest-cov`, `ruff`. Check each name on PyPI before installing. `pip install -e ".[dev]"`.
4. **Skeleton.** Every package of SPEC §1 with an `__init__.py`; `LICENSE` (MIT, "the project contributors"); `tta/config.py` (`TTA_ENV`, `TTA_MODE`, `TTA_DATA_DIR`, `TTA_DB_PATH`, `TTA_VALIO_CALL_BUDGET`, the Valio and Gemini variables; loads `.env` when present; a secret never appears in `repr`).
5. **Contracts** in `src/tta/contracts/`, straight from SPEC §2–§9: `common.py` (enums, identity), `request.py`, `product.py`, `allergen.py`, `availability.py`, `offer.py`, `policy.py`, `order.py`, `audit.py`, `errors.py` (one typed error per problem type), `ports.py` (protocols: `ValioGateway`, `Clock`, `Catalog`, `PolicyEngine`, `OfferBuilder`, `OfferRevalidator`, `Store`, `AuditSink`, `RequestParser`, `AgentRunner`). Frozen models, `Decimal`, JSON Schema exportable. A test imports every contract and exports every schema.
6. **Fixtures.**
   - Copy Friday's 1,000-product sample (availability and price bodies with their `timeNow`) from the session scratchpad into `fixtures/valio/2026-11-13-sample/`. Check first that no file holds a key or a request header.
   - **New capture** → `fixtures/valio/2026-11-14-demo/`: one price call and one availability call for: every product in category 10400; the category of `464056` and `468319`; `473609`, its listed substitutes and its category; the categories of `464744` and `466988`. At most 1,000 ids. Store bodies, the id list and `timeNow`; nothing else.
   - `tests/conftest.py`: fixture loaders, a pinned clock per capture, a session-scoped raw product loader.
7. **Check.** `.venv/bin/python -m pytest -q` passes; commit `feat: project skeleton, contracts and fixtures`.
8. Update `STATUS.md`, including the live-call count (2).
