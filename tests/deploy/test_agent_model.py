"""The Modal app that serves the agent's model (task AG): what it would deploy, checked offline.

Loading `deploy/agent_model.py` defines the app, its image, its Volumes and a reference to its Secret, all lazily:
nothing is sent to Modal and no Modal credentials are needed. Nothing here deploys, downloads or calls a model.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from types import ModuleType

import modal
import pytest

from tta.config import REPO_ROOT

PATH = REPO_ROOT / "deploy" / "agent_model.py"


@pytest.fixture(scope="module")
def module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("tta_deploy_agent_model", PATH)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = loaded
    spec.loader.exec_module(loaded)
    return loaded


def test_it_is_one_modal_server_with_one_gpu_a_key_and_two_volumes(module: ModuleType) -> None:
    assert isinstance(module.app, modal.App) and module.app.name == "trusted-trade-agent-model"
    assert isinstance(module.AgentModel, modal.Server)
    assert (module.GPU, module.GPU_COUNT, module.MAX_CONTAINERS) == ("L40S", 1, 1)
    assert isinstance(module.key, modal.Secret)
    assert isinstance(module.hf_cache, modal.Volume) and isinstance(module.vllm_cache, modal.Volume)
    assert 0 < module.TARGET_CONCURRENT_REQUESTS <= module.MAX_CONCURRENT_REQUESTS
    assert 10 * 60 <= module.SCALEDOWN_SECONDS <= 60 * 60  # long enough for a demo, never left on for the night


def test_the_command_serves_the_pinned_model_with_tool_calling_and_carries_no_key(module: ModuleType) -> None:
    command = module.serve_command()

    assert command[:3] == ["vllm", "serve", "Qwen/Qwen2.5-14B-Instruct"]
    assert command[command.index("--revision") + 1] == module.MODEL_REVISION and len(module.MODEL_REVISION) == 40
    assert command[command.index("--served-model-name") + 1] == "qwen2.5-14b-instruct"
    assert "--enable-auto-tool-choice" in command
    assert command[command.index("--tool-call-parser") + 1] == "hermes"
    assert "--api-key" not in command  # vLLM reads VLLM_API_KEY from the Modal Secret
    assert module.KEY_NAME == "VLLM_API_KEY"


def test_the_container_refuses_to_serve_without_a_key(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VLLM_API_KEY", raising=False)
    started: list[object] = []
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: started.append(args))
    served = module.AgentModel._get_user_cls()()  # the plain class behind the Modal server

    with pytest.raises(RuntimeError, match="VLLM_API_KEY"):
        served.start()

    assert started == []


def test_the_dry_run_prints_the_plan_and_sends_nothing(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VLLM_API_KEY", "sentinel-key-not-a-real-one")
    monkeypatch.setenv("TTA_AGENT_API_KEY", "sentinel-key-not-a-real-one")
    lines: list[str] = []

    assert module.dry_run(lines.append) == 0

    printed = "\n".join(lines)
    assert "sentinel-key-not-a-real-one" not in printed
    for said in ("Qwen/Qwen2.5-14B-Instruct", "Apache-2.0", "L40S", "hermes", "trusted-trade-agent-model-key",
                 "TTA_AGENT_PROVIDER=openai_compatible", "TTA_AGENT_MODEL=qwen2.5-14b-instruct", "an hour"):
        assert said in printed
    assert lines[-1] == "Dry run: nothing was sent to Modal and nothing was deployed."


def test_the_cost_is_the_pricing_pages_figures_for_what_is_asked(module: ModuleType) -> None:
    gpu, cores, memory = 0.000542 * 3600, 0.0000131 * 4 * 3600, 0.00000222 * 32 * 3600

    assert module.warm_cost_per_hour() == pytest.approx(gpu + cores + memory)
    assert 2.3 < module.warm_cost_per_hour() < 2.5


def test_the_gateway_names_the_model_as_the_server_serves_it(module: ModuleType) -> None:
    from tta.config import Settings

    settings = Settings.for_tests(
        tta_agent_provider="openai_compatible", tta_agent_base_url="https://w--app-agentmodel.modal.run/v1",
        tta_agent_model=module.SERVED_MODEL_NAME,
    )
    assert settings.has_agent_model and settings.describe()["agent_model"] == "qwen2.5-14b-instruct"
