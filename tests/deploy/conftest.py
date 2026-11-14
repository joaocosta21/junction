"""Fixtures for the deployment tests: the two modules of `deploy/`, loaded by path, and sentinel secret values.

Loading `deploy/modal_app.py` defines the Modal app, its image, its Volume and its Secret, all lazily: nothing is
sent to Modal and no Modal credentials are needed. On the deploying machine the module reads the three secret
values through `tta.config.get_settings()`; here that function is replaced first by settings built for tests,
with sentinel values, so no test reads `.env`.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import modal
import pytest

import tta.config
from tta.config import REPO_ROOT, Settings

DEPLOY_DIR = REPO_ROOT / "deploy"


@dataclass(frozen=True)
class Sentinels:
    """Values that stand for secrets: a test can tell where each one went, and none is real."""

    valio_key: str = "sentinel-valio-key-not-a-real-one"
    gemini_key: str = "sentinel-gemini-key-not-a-real-one"
    base_url: str = "https://sentinel.example/api"

    def settings(self, **overrides: object) -> Settings:
        values: dict[str, object] = {
            "valio_aimo_api_key": self.valio_key,
            "gemini_api_key": self.gemini_key,
            "valio_aimo_base_url": self.base_url,
        }
        values.update(overrides)
        return Settings.for_tests(**values)


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses look their module up here
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sentinels() -> Sentinels:
    return Sentinels()


@pytest.fixture
def deploy_dir() -> Path:
    return DEPLOY_DIR


@pytest.fixture
def modal_app(monkeypatch: pytest.MonkeyPatch, sentinels: Sentinels) -> Iterator[ModuleType]:
    monkeypatch.setattr(tta.config, "get_settings", sentinels.settings)
    module = _load(DEPLOY_DIR / "modal_app.py", "tta_deploy_modal_app")
    yield module
    sys.modules.pop("tta_deploy_modal_app", None)


@pytest.fixture
def check() -> Iterator[ModuleType]:
    module = _load(DEPLOY_DIR / "check.py", "tta_deploy_check")
    yield module
    sys.modules.pop("tta_deploy_check", None)


@pytest.fixture
def modal_app_in_the_container(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """The module as the container imports it: `modal.is_local()` is false there, and no setting may be read."""

    def must_not_be_called() -> Settings:
        raise AssertionError("settings were read inside the container")

    monkeypatch.setattr(tta.config, "get_settings", must_not_be_called)
    monkeypatch.setattr(modal, "is_local", lambda: False)
    module = _load(DEPLOY_DIR / "modal_app.py", "tta_deploy_modal_app_remote")
    yield module
    sys.modules.pop("tta_deploy_modal_app_remote", None)
