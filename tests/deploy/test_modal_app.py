"""`deploy/modal_app.py`: what the deployment holds, which values reach Modal, and how it scales (task T14).

No test talks to Modal or needs its credentials, and none reads `.env`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from importlib.metadata import version
from pathlib import Path
from types import ModuleType
from typing import Any

import modal
import pytest

from tta.config import REPO_ROOT, Settings
from tta.contracts.common import DataSource

THREE_NAMES = {"VALIO_AIMO_API_KEY", "VALIO_AIMO_BASE_URL", "GEMINI_API_KEY"}
NEVER_IN_THE_IMAGE = (".env", ".claude", "var", ".git", ".venv")
PRODUCT_FILE = "valio_aimo_junction26_product_data.json"
RELIABILITY_FILE = "valio_aimo_junction26_delivery_reliability.csv"
CARBON_FILE = "valio_aimo_junction26_carbon_footprint.csv"
IMPORT_IN_A_CLEAN_PROCESS = """
import importlib.util, sys
import tta.config
tta.config.get_settings = lambda: tta.config.Settings.for_tests()
spec = importlib.util.spec_from_file_location("modal_app", sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules["modal_app"] = module
spec.loader.exec_module(module)
print(module.app.name, type(module.web).__name__)
"""


# --- the module -------------------------------------------------------------------------------------------------


def test_the_module_defines_the_app_without_modal_credentials_and_from_any_folder(
    tmp_path: Path, deploy_dir: Path
) -> None:
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(tmp_path),
        "MODAL_CONFIG_PATH": str(tmp_path / "no-modal-config.toml"),
    }
    done = subprocess.run(  # noqa: S603 - this interpreter and a file of the repository
        [sys.executable, "-c", IMPORT_IN_A_CLEAN_PROCESS, str(deploy_dir / "modal_app.py")],
        cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=120, check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.split() == ["trusted-trade-agents", "Function"]


def test_one_container_at_most_that_scales_to_zero(modal_app: ModuleType) -> None:
    assert modal_app.app.name == modal_app.APP_NAME == "trusted-trade-agents"
    assert isinstance(modal_app.web, modal.Function)
    assert modal_app.MAX_CONTAINERS == 1
    assert modal_app.MIN_CONTAINERS == 0
    assert 2 <= modal_app.SCALEDOWN_SECONDS <= 3600  # the range Modal accepts
    assert modal_app.MAX_CONCURRENT_REQUESTS > 1


# --- the secret -------------------------------------------------------------------------------------------------


def test_the_secret_holds_exactly_the_three_values_the_app_reads(modal_app: ModuleType, sentinels: Any) -> None:
    settings = sentinels.settings(
        database_url="sentinel-database-url", context_dev_api_key="sentinel-context-key", tta_tokens='{"t": 1}'
    )

    values = modal_app.secret_values(settings)

    assert values == {
        "VALIO_AIMO_API_KEY": sentinels.valio_key,
        "VALIO_AIMO_BASE_URL": sentinels.base_url,
        "GEMINI_API_KEY": sentinels.gemini_key,
    }
    assert set(modal_app.SECRET_NAMES) == THREE_NAMES


def test_a_value_that_is_not_set_is_left_out(modal_app: ModuleType) -> None:
    assert modal_app.secret_values(Settings.for_tests()) == {}
    assert modal_app.secret_values(Settings.for_tests(valio_aimo_api_key="  ", gemini_api_key="")) == {}


def test_the_base_url_goes_only_when_it_was_set(modal_app: ModuleType, sentinels: Any) -> None:
    only_url = Settings.for_tests(valio_aimo_base_url=sentinels.base_url)
    only_gemini = Settings.for_tests(gemini_api_key=sentinels.gemini_key)

    assert modal_app.secret_values(only_url) == {"VALIO_AIMO_BASE_URL": sentinels.base_url}
    assert modal_app.secret_values(only_gemini) == {"GEMINI_API_KEY": sentinels.gemini_key}


def test_on_the_deploying_machine_the_values_come_through_tta_config(modal_app: ModuleType, sentinels: Any) -> None:
    assert modal_app.secret_env(is_local=True) == modal_app.secret_values(sentinels.settings())


def test_inside_the_container_no_setting_is_read(modal_app: ModuleType) -> None:
    def must_not_be_called() -> Settings:
        raise AssertionError("settings were read inside the container")

    assert modal_app.secret_env(is_local=False, read_settings=must_not_be_called) == {}


def test_inside_the_container_the_module_loads_without_reading_a_setting(
    modal_app_in_the_container: ModuleType,
) -> None:
    assert isinstance(modal_app_in_the_container.web, modal.Function)
    assert modal_app_in_the_container.secret_env(is_local=False) == {}


# --- the environment of the image -------------------------------------------------------------------------------


def test_no_secret_is_in_the_image_environment(modal_app: ModuleType, sentinels: Any) -> None:
    environment = modal_app.IMAGE_ENV

    assert not THREE_NAMES & set(environment)
    assert all(isinstance(value, str) for value in environment.values())
    for sentinel in (sentinels.valio_key, sentinels.gemini_key, sentinels.base_url):
        assert all(sentinel not in value for value in environment.values())


def test_the_image_environment_is_the_public_demo_in_live_mode(modal_app: ModuleType) -> None:
    settings = Settings.for_tests(
        **{name.lower(): value for name, value in modal_app.IMAGE_ENV.items() if name.startswith("TTA_")}
    )
    app_root = Path(modal_app.APP_ROOT)

    assert settings.tta_env == "demo" and settings.is_demo_environment
    assert settings.tta_mode is DataSource.LIVE
    assert settings.tta_data_dir == Path(modal_app.VOLUME_MOUNT)
    assert settings.db_path == Path(modal_app.LOCAL_DB)
    assert not settings.db_path.is_relative_to(modal_app.VOLUME_MOUNT)  # SQLite works on local disk
    assert settings.tta_product_file == app_root / PRODUCT_FILE
    assert settings.tta_reliability_file == app_root / RELIABILITY_FILE
    assert settings.tta_carbon_file == app_root / CARBON_FILE
    assert settings.replay_capture_dir == app_root / "fixtures" / "valio" / "2026-11-14-demo"
    assert modal_app.IMAGE_ENV["PYTHONPATH"] == f"{modal_app.APP_ROOT}/src"


# --- what goes into the image -----------------------------------------------------------------------------------


def _relative(modal_app: ModuleType, root: Path) -> set[tuple[str, str, bool]]:
    return {
        (source.local.relative_to(root).as_posix(), source.remote, source.is_dir)
        for source in modal_app.image_sources(root)
    }


def test_the_image_holds_the_package_the_data_files_and_the_fixtures(modal_app: ModuleType) -> None:
    app_root = modal_app.APP_ROOT
    expected = {
        ("src/tta", f"{app_root}/src/tta", True),
        (PRODUCT_FILE, f"{app_root}/{PRODUCT_FILE}", False),
        (RELIABILITY_FILE, f"{app_root}/{RELIABILITY_FILE}", False),
        (CARBON_FILE, f"{app_root}/{CARBON_FILE}", False),
        ("fixtures/valio", f"{app_root}/fixtures/valio", True),
        ("fixtures/agent", f"{app_root}/fixtures/agent", True),
    }
    if (REPO_ROOT / "docs" / "ASSUMPTIONS.md").is_file():
        expected.add(("docs/ASSUMPTIONS.md", f"{app_root}/docs/ASSUMPTIONS.md", False))

    assert _relative(modal_app, REPO_ROOT) == expected


def test_the_assumptions_page_goes_in_only_when_it_exists(modal_app: ModuleType, tmp_path: Path) -> None:
    assert not any(local == "docs/ASSUMPTIONS.md" for local, _, _ in _relative(modal_app, tmp_path))

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ASSUMPTIONS.md").write_text("# Assumptions\n", encoding="utf-8")

    assert ("docs/ASSUMPTIONS.md", f"{modal_app.APP_ROOT}/docs/ASSUMPTIONS.md", False) in _relative(
        modal_app, tmp_path
    )


def _uploaded(modal_app: ModuleType, folder: Path) -> list[Path]:
    """The files of a folder that Modal uploads: it walks the folder and asks `ignore` of each relative path."""
    files = (path.relative_to(folder) for path in folder.rglob("*") if path.is_file())
    return sorted(path for path in files if not modal_app.skipped(path))


def test_nothing_else_from_the_repository_goes_in(modal_app: ModuleType) -> None:
    for source in modal_app.image_sources(REPO_ROOT):
        uploaded = _uploaded(modal_app, source.local) if source.is_dir else [Path(source.local.name)]
        local_parts = source.local.relative_to(REPO_ROOT).parts
        for path in uploaded:
            parts = (*local_parts, *path.parts)
            assert not set(parts) & set(NEVER_IN_THE_IMAGE), parts
            assert not any(part.startswith(".") for part in parts), parts


@pytest.mark.parametrize(
    "path",
    ["api/__pycache__", "api/__pycache__/app.cpython-313.pyc", "config.pyc", ".DS_Store", "ui/.hidden/x.html",
     ".env", "ui/templates/.base.html.swp"],
)
def test_caches_and_hidden_files_stay_out(modal_app: ModuleType, path: str) -> None:
    assert modal_app.skipped(Path(path))


def test_every_file_the_package_reads_goes_in(modal_app: ModuleType) -> None:
    package = REPO_ROOT / "src" / "tta"
    uploaded = {path.as_posix() for path in _uploaded(modal_app, package)}
    wanted = {
        path.relative_to(package).as_posix()
        for suffix in ("*.py", "*.yaml", "*.html", "*.css", "*.js")
        for path in package.rglob(suffix)
        if "__pycache__" not in path.parts
    }

    assert {"api/demo_tokens.yaml", "catalog/product_types.yaml", "ui/templates/base.html",
            "ui/static/app.css", "ui/static/app.js", "config.py"} <= wanted
    assert wanted <= uploaded
    assert not any(name.endswith(".pyc") or "__pycache__" in name for name in uploaded)


# --- the libraries ----------------------------------------------------------------------------------------------


def _name(requirement: str) -> str:
    for separator in ("[", "=", "<", ">", "~", "!", ";", " "):
        requirement = requirement.split(separator, 1)[0]
    return requirement.strip().lower().replace("_", "-")


def test_the_image_installs_the_versions_the_tests_ran_with(modal_app: ModuleType) -> None:
    for pin in modal_app.PINNED:
        name, pinned = pin.split("==")
        assert version(_name(name)) == pinned, pin


def test_every_library_the_package_declares_is_pinned(modal_app: ModuleType) -> None:
    declared = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["dependencies"]
    pinned = {_name(pin) for pin in modal_app.PINNED}

    assert {_name(requirement) for requirement in declared} - set(modal_app.NOT_INSTALLED) <= pinned
    assert set(modal_app.NOT_INSTALLED) == {"modal", "uvicorn"}
