"""The language model behind the buyer's agent, served on a Modal GPU (task AG).

What it is: one open-weights instruct model, Qwen2.5-14B-Instruct, served by vLLM's OpenAI-compatible server on
one L40S GPU, behind a public address with a bearer key. The gateway's buyer agent asks it to read a pasted
sentence into a typed request and to choose the gateway's function calls (`tta.agent.openai_compat`,
`TTA_AGENT_PROVIDER=openai_compatible`). What it is not: no fine-tuning, no training, no data of ours in the
image or on the Volume; the weights are the published ones, at a pinned revision. Nothing is claimed here that
did not run: this file was written on 14 Nov 2026 without deploying it, and the first deploy is the first run.

    .venv/bin/python deploy/agent_model.py --dry-run      # offline: prints what would be deployed, sends nothing
    .venv/bin/modal deploy deploy/agent_model.py          # the deploy (after the Secret exists)

Scores on the 30% "working end-to-end demo" (a real model reads and calls, with nobody else's credits) and on
Modal's brief ("Serve an open model on a GPU"). The model decides nothing about products, prices or approvals:
the gateway does, and the fixed rules check every reading (`tta.agent.held`, `tta.agent.fallback`).

Choices, each from a page read on 14 Nov 2026:
- **Model: `Qwen/Qwen2.5-14B-Instruct`**, licence Apache-2.0, not gated, 14.7 billion parameters in BF16 (its
  Hugging Face model card). vLLM's tool-calling page lists Qwen2.5 under the `hermes` parser and the model card
  names vLLM for deployment and stresses structured JSON output and "over 29 languages". About 29.5 GB of weights
  (14.7 billion parameters at two bytes each: our arithmetic, the card gives no size).
- **GPU: one L40S** (48 GB): the weights fit with room for the context; a 24 GB L4 or A10 would not hold them.
  Modal's own vLLM example serves a 26B model on an H200; a 14B model does not need one.
- **Tool calling:** `--enable-auto-tool-choice --tool-call-parser hermes` (vLLM, "Tool calling").
- **The key:** vLLM's `VLLM_API_KEY` (the same as `--api-key`), read from the Modal Secret `SECRET_NAME`; the
  gateway sends the same value as `TTA_AGENT_API_KEY`. vLLM's page says the key protects the paths under `/v1`
  only: `/health` and `/metrics` answer without it, and show no request and no text. The Modal address itself is
  public (`unauthenticated=True`): Modal's own proxy tokens would be a second secret in a second header, which
  an OpenAI-compatible client does not send.
- **Weights on a Volume** (`huggingface-cache`, mounted at the Hugging Face cache): downloaded at the first start,
  read from the Volume afterwards. A second Volume keeps vLLM's own cache.
- **Scale to zero** after `SCALEDOWN_SECONDS` idle; at most one container; at most `MAX_CONCURRENT_REQUESTS` at a
  time, beyond which Modal answers 429. While a container starts, Modal answers 503 (its "Servers" guide), so the
  gateway's first sentence after an idle time is read by the fixed rules, and says so.
- **`FAST_BOOT`** adds `--enforce-eager`, as Modal's example does for a server that often starts cold: a quicker
  start for slower generation.

Names used, as the installed Modal client has them (1.6.4, checked with `inspect`) and as Modal's "Servers" guide
and its vLLM example use them: `modal.App`, `@app.server(image=, gpu=, secrets=, volumes=, scaledown_window=,
startup_timeout=, port=, max_containers=, target_concurrency=, max_concurrency=, unauthenticated=, cpu=, memory=)`,
`@modal.enter()`, `@modal.exit()`, `modal.Image.from_registry(..., add_python=)`, `.entrypoint([])`,
`.uv_pip_install`, `.env`, `modal.Volume.from_name(..., create_if_missing=True)`,
`modal.Secret.from_name(..., required_keys=[...])`. The image and the pinned `vllm` and `transformers` versions are
those of Modal's example as read that day.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable

import modal

APP_NAME = "trusted-trade-agent-model"
SERVER_NAME = "AgentModel"
SECRET_NAME = "trusted-trade-agent-model-key"  # noqa: S105 - the name of the Secret, not its value
KEY_NAME = "VLLM_API_KEY"  # the environment variable vLLM reads its key from

MODEL_NAME = "Qwen/Qwen2.5-14B-Instruct"
MODEL_REVISION = "cf98f3b3bbb457ad9e2bb7baf9a0125b6b88caa8"  # the repository's head on 14 Nov 2026
MODEL_LICENCE = "Apache-2.0"
SERVED_MODEL_NAME = "qwen2.5-14b-instruct"  # TTA_AGENT_MODEL: the name a request and a reading's sentence carry
TOOL_CALL_PARSER = "hermes"
MAX_MODEL_TOKENS = 16384  # the instruction with its tables, a run's history and the answer fit several times over

GPU = "L40S"
GPU_COUNT = 1
CPU_CORES = 4.0
MEMORY_MIB = 32768
VLLM_PORT = 8000
MINUTES = 60
SCALEDOWN_SECONDS = 20 * MINUTES  # a demo with pauses stays warm; then the GPU is released
STARTUP_TIMEOUT_SECONDS = 20 * MINUTES  # the first start downloads the weights to the Volume
MAX_CONTAINERS = 1
TARGET_CONCURRENT_REQUESTS = 4
MAX_CONCURRENT_REQUESTS = 8  # above it Modal answers 429, which the gateway treats as out of reach
FAST_BOOT = True

BASE_IMAGE = "nvidia/cuda:12.9.0-devel-ubuntu22.04"
IMAGE_PYTHON = "3.12"
PINNED = ("vllm==0.21.0", "transformers==5.8.1")
IMAGE_ENV = {"HF_XET_HIGH_PERFORMANCE": "1"}
HF_CACHE_VOLUME, HF_CACHE_PATH = "huggingface-cache", "/root/.cache/huggingface"
VLLM_CACHE_VOLUME, VLLM_CACHE_PATH = "vllm-cache", "/root/.cache/vllm"

# Modal's pricing page as read on 14 Nov 2026, per second: L40S, a CPU core, a GiB of memory.
PRICES_READ_ON = "14 Nov 2026"
GPU_PER_SECOND, CPU_CORE_PER_SECOND, MEMORY_GIB_PER_SECOND = 0.000542, 0.0000131, 0.00000222
SECONDS_PER_HOUR, MIB_PER_GIB = 3600, 1024

NO_KEY_IN_CONTAINER = f"{KEY_NAME} is not set in the container: the model is not served without a key."


def serve_command() -> list[str]:
    """The `vllm serve` command. The key is not on it: vLLM reads it from `VLLM_API_KEY`."""
    return [
        "vllm", "serve", MODEL_NAME,
        "--revision", MODEL_REVISION,
        "--served-model-name", SERVED_MODEL_NAME,
        "--host", "0.0.0.0",  # noqa: S104 - inside the container; Modal's proxy is the only way in
        "--port", str(VLLM_PORT),
        "--max-model-len", str(MAX_MODEL_TOKENS),
        "--tensor-parallel-size", str(GPU_COUNT),
        "--enable-auto-tool-choice",
        "--tool-call-parser", TOOL_CALL_PARSER,
        "--uvicorn-log-level=info",
        "--enforce-eager" if FAST_BOOT else "--no-enforce-eager",
    ]


def warm_cost_per_hour() -> float:
    """What one warm container costs an hour at the prices above: the GPU, the cores and the memory asked for."""
    per_second = (
        GPU_PER_SECOND * GPU_COUNT + CPU_CORE_PER_SECOND * CPU_CORES
        + MEMORY_GIB_PER_SECOND * MEMORY_MIB / MIB_PER_GIB
    )
    return per_second * SECONDS_PER_HOUR


def plan() -> list[str]:
    """What a deploy would create, line by line. No value of any secret: only the Secret's name."""
    return [
        f"Modal app {APP_NAME}: one server, {SERVER_NAME}, on port {VLLM_PORT}.",
        f"Model: {MODEL_NAME} at revision {MODEL_REVISION} ({MODEL_LICENCE}), served as {SERVED_MODEL_NAME}.",
        f"GPU: {GPU_COUNT} x {GPU}; {CPU_CORES:g} cores; {MEMORY_MIB // MIB_PER_GIB} GiB of memory.",
        f"Image: {BASE_IMAGE}, Python {IMAGE_PYTHON}, {', '.join(PINNED)}.",
        f"Volumes: {HF_CACHE_VOLUME} at {HF_CACHE_PATH} (the weights), {VLLM_CACHE_VOLUME} at {VLLM_CACHE_PATH}.",
        f"Key: the Modal Secret {SECRET_NAME} must hold {KEY_NAME}; paths under /v1 need it as a bearer key.",
        f"Scaling: at most {MAX_CONTAINERS} container, to zero after {SCALEDOWN_SECONDS // MINUTES} minutes idle; "
        f"at most {MAX_CONCURRENT_REQUESTS} requests at a time; up to {STARTUP_TIMEOUT_SECONDS // MINUTES} minutes "
        "to start.",
        f"Command: {' '.join(serve_command())}",
        f"Cost while warm: about ${warm_cost_per_hour():.2f} an hour (Modal's pricing page, read {PRICES_READ_ON}: "
        f"{GPU} ${GPU_PER_SECOND:.6f}/s, a core ${CPU_CORE_PER_SECOND:.7f}/s, a GiB ${MEMORY_GIB_PER_SECOND:.8f}/s). "
        "Nothing while scaled to zero, besides the Volumes.",
        f"Gateway settings: TTA_AGENT_PROVIDER=openai_compatible TTA_AGENT_MODEL={SERVED_MODEL_NAME} "
        "TTA_AGENT_BASE_URL=<the address the deploy prints>/v1 TTA_AGENT_API_KEY=<the Secret's value>.",
    ]


def dry_run(out: Callable[[str], None] = print) -> int:
    """Prints the plan. Sends nothing: no Modal call, no download."""
    for line in plan():
        out(line)
    out("Dry run: nothing was sent to Modal and nothing was deployed.")
    return 0


image = (
    modal.Image.from_registry(BASE_IMAGE, add_python=IMAGE_PYTHON)
    .entrypoint([])
    .uv_pip_install(*PINNED)
    .env(IMAGE_ENV)
)
app = modal.App(APP_NAME)
hf_cache = modal.Volume.from_name(HF_CACHE_VOLUME, create_if_missing=True)
vllm_cache = modal.Volume.from_name(VLLM_CACHE_VOLUME, create_if_missing=True)
key = modal.Secret.from_name(SECRET_NAME, required_keys=[KEY_NAME])


@app.server(
    image=image,
    gpu=f"{GPU}:{GPU_COUNT}",
    cpu=CPU_CORES,
    memory=MEMORY_MIB,
    secrets=[key],
    volumes={HF_CACHE_PATH: hf_cache, VLLM_CACHE_PATH: vllm_cache},
    scaledown_window=SCALEDOWN_SECONDS,
    startup_timeout=STARTUP_TIMEOUT_SECONDS,
    port=VLLM_PORT,
    max_containers=MAX_CONTAINERS,
    target_concurrency=TARGET_CONCURRENT_REQUESTS,
    max_concurrency=MAX_CONCURRENT_REQUESTS,
    unauthenticated=True,  # Modal's edge lets requests through; vLLM asks for the key on every path under /v1
    name=SERVER_NAME,
)
class AgentModel:
    """vLLM's OpenAI-compatible server for the one model above."""

    @modal.enter()
    def start(self) -> None:
        if not os.environ.get(KEY_NAME, "").strip():
            raise RuntimeError(NO_KEY_IN_CONTAINER)
        self.process = subprocess.Popen(serve_command())  # noqa: S603 - our own fixed command, no shell

    @modal.exit()
    def stop(self) -> None:
        self.process.terminate()


if __name__ == "__main__":  # plain Python: the offline dry run only
    parser = argparse.ArgumentParser(description="The agent's model on Modal: the offline dry run.")
    parser.add_argument("--dry-run", action="store_true", required=True)
    parser.parse_args()
    sys.exit(dry_run())
