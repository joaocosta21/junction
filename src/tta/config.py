"""Settings from the environment (SPEC section 10).

Secrets are `SecretStr`: they never appear in a `repr`, a log line or an error message. Code asks
`settings.has_...` to learn whether a value is set, and unwraps a secret only where it is sent to
the service it belongs to.
"""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from tta.contracts.common import DataSource

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VALIO_BASE_URL = "https://junction26.valioaimo.fi/api"
DEFAULT_CALL_BUDGET = 150
DEMO_ENVIRONMENTS = ("dev", "demo")
MAX_TRUSTED_PROXY_HOPS = 10
_SECRET_FIELDS = (
    "valio_aimo_api_key", "gemini_api_key", "database_url", "context_dev_api_key", "tta_tokens", "tta_signing_key",
    "tta_agent_api_key",
)
AGENT_PROVIDER_NONE, AGENT_PROVIDER_OPENAI, AGENT_PROVIDER_GEMINI = "none", "openai_compatible", "gemini"
AGENT_URL_SCHEMES = ("http", "https")
BAD_AGENT_URL = (
    "TTA_AGENT_BASE_URL must be an http or https address with a host and no user name, password, query or "
    "fragment, for example https://host.example/v1. The key goes in TTA_AGENT_API_KEY."
)


def _is_set(secret: SecretStr | None) -> bool:
    return bool(secret is not None and secret.get_secret_value().strip())


class Settings(BaseSettings):
    """Read once from the environment and, when present, the repository's `.env`."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore", frozen=True,
        hide_input_in_errors=True,  # a refused value is never repeated: it may be an address with a secret in it
    )

    # Fails closed: with TTA_ENV unset the app is in `prod`, where no demo token exists and the app refuses to
    # start without TTA_TOKENS. Set TTA_ENV=dev locally and TTA_ENV=demo for the public demo.
    tta_env: Literal["dev", "demo", "prod"] = "prod"
    tta_mode: DataSource = DataSource.REPLAY
    tta_data_dir: Path = REPO_ROOT / "var"
    tta_db_path: Path | None = None  # default: <data dir>/tta.sqlite3
    tta_valio_call_budget: int = Field(default=DEFAULT_CALL_BUDGET, ge=0)
    tta_fixtures_dir: Path = REPO_ROOT / "fixtures"
    tta_replay_capture: str = "2026-11-14-demo"
    # The demo clock: an instant with an offset, for example 2026-11-12T14:15:00+02:00. Honoured in replay only
    # and in dev and demo only: it replaces the recording's own instant as the clock every order cut-off is
    # compared with. Unset: the recording's instant. Valio Aimo, 14 Nov 2026: "this is all static data so we can
    # chose the date". The audit trail keeps the real time whatever is set here.
    tta_demo_clock: AwareDatetime | None = None
    tta_product_file: Path = REPO_ROOT / "valio_aimo_junction26_product_data.json"
    tta_reliability_file: Path = REPO_ROOT / "valio_aimo_junction26_delivery_reliability.csv"
    tta_carbon_file: Path = REPO_ROOT / "valio_aimo_junction26_carbon_footprint.csv"
    # The customer number does not change the mock's answers (AIMO/docs/API.md section 3).
    tta_customer: str = "123"
    tta_gemini_model: str | None = None  # overrides the model the agent package chooses
    # The language model behind the buyer's agent (task AG). `openai_compatible`: an OpenAI-compatible
    # chat-completions endpoint with tool calling, for example the open-weights model of `deploy/agent_model.py` on
    # Modal; it needs the base URL (ending in /v1) and the model name the endpoint serves. `gemini`: the Gemini
    # API, with GEMINI_API_KEY. `none`: no provider is chosen, and, as before this setting existed, Gemini is
    # asked only when GEMINI_API_KEY is set. With no model, a recording or the fixed rules read a request.
    tta_agent_provider: Literal["none", "openai_compatible", "gemini"] = "none"
    tta_agent_base_url: str | None = None  # never shown: `/healthz` says only whether it is set
    tta_agent_model: str | None = None
    tta_agent_api_key: SecretStr | None = None  # sent as the bearer key of the endpoint and nowhere else
    tta_tokens: SecretStr | None = None  # JSON map of bearer token to identity; required outside dev and demo
    # How many proxies of ours stand in front of the app, each appending the address it saw to X-Forwarded-For.
    # 0: no forwarded header is believed and the peer address is the visitor (Modal: the peer is the visitor).
    tta_trusted_proxy_hops: int = Field(default=0, ge=0, le=MAX_TRUSTED_PROXY_HOPS)
    # Origins of web pages that may call the MCP endpoint, comma-separated, for example
    # "https://inspector.example,https://host.example:8443". Pages on this machine are always allowed and a request
    # with no Origin header (an agent, a program) is always served (`tta.api.mcp_origin`, MCP revision 2026-07-28).
    tta_mcp_allowed_origins: str = ""
    # The PostgreSQL schema of the order book, a plain lower-case identifier. Blank: the schema of the environment
    # (`tta.store.postgres.schema_for`, which reads this setting and refuses a name the store does not take).
    tta_db_schema: str = ""
    # The key the gateway signs every offer and order record with: the 32-byte seed of an Ed25519 key as base64url
    # (`tta.api.signing`). Unset: a demo key is generated at each start and every signature says so.
    tta_signing_key: SecretStr | None = None
    # Valio Aimo's own suggestion on an offer (the brief's "proactive selling agent", decision B31): a related
    # product, checked like any other, shown last and apart, never added to an order. False switches it off; the
    # suggestions computed from the buyer's own orders stay.
    tta_supplier_suggestions: bool = True
    # In dev and demo the standing orders of the four demo customers' files are set up in the shared order book
    # when the gateway starts, with their synthetic past renewals (P1 C3), once per database. False leaves the
    # book empty at start, as `Settings.for_tests` does: a test that wants them asks for them.
    tta_customer_standing_orders: bool = True

    valio_aimo_api_key: SecretStr | None = None
    valio_aimo_base_url: str = DEFAULT_VALIO_BASE_URL
    gemini_api_key: SecretStr | None = None
    database_url: SecretStr | None = None
    context_dev_api_key: SecretStr | None = None

    @field_validator("tta_demo_clock", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: Any) -> Any:
        """`TTA_DEMO_CLOCK=` with nothing after it reads as unset, as a deploy file may leave it."""
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("tta_agent_base_url", "tta_agent_model", mode="before")
    @classmethod
    def _blank_is_none(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("tta_agent_base_url")
    @classmethod
    def _a_plain_address(cls, value: str | None) -> str | None:
        """An address that can hold no secret: the value itself is never repeated in the refusal."""
        if value is None:
            return None
        parts = urlsplit(value.strip())
        plain = parts.scheme in AGENT_URL_SCHEMES and parts.hostname and not (
            parts.username or parts.password or parts.query or parts.fragment
        )
        if not plain:
            raise ValueError(BAD_AGENT_URL)
        return value.strip().rstrip("/")

    @property
    def demo_clock(self) -> datetime | None:
        """The demo clock in force: the instant set, in replay; None when it is unset or the mode is live."""
        return self.tta_demo_clock if self.tta_mode is DataSource.REPLAY else None

    @property
    def db_path(self) -> Path:
        return self.tta_db_path or self.tta_data_dir / "tta.sqlite3"

    @property
    def valio_fixtures_dir(self) -> Path:
        return self.tta_fixtures_dir / "valio"

    @property
    def replay_capture_dir(self) -> Path:
        return self.valio_fixtures_dir / self.tta_replay_capture

    @property
    def is_demo_environment(self) -> bool:
        return self.tta_env in DEMO_ENVIRONMENTS

    @property
    def has_valio_key(self) -> bool:
        return _is_set(self.valio_aimo_api_key)

    @property
    def has_gemini_key(self) -> bool:
        return _is_set(self.gemini_api_key)

    @property
    def has_agent_key(self) -> bool:
        return _is_set(self.tta_agent_api_key)

    @property
    def has_agent_endpoint(self) -> bool:
        """True when the OpenAI-compatible provider is chosen and its address and model name are both set."""
        return bool(
            self.tta_agent_provider == AGENT_PROVIDER_OPENAI and self.tta_agent_base_url and self.tta_agent_model
        )

    @property
    def has_agent_model(self) -> bool:
        """True when a language model is asked first: the OpenAI-compatible endpoint, or Gemini with its key."""
        if self.tta_agent_provider == AGENT_PROVIDER_OPENAI:
            return self.has_agent_endpoint
        return self.has_gemini_key

    @property
    def has_database_url(self) -> bool:
        return _is_set(self.database_url)

    @property
    def has_context_dev_key(self) -> bool:
        return _is_set(self.context_dev_api_key)

    @property
    def has_tokens(self) -> bool:
        return _is_set(self.tta_tokens)

    @property
    def has_signing_key(self) -> bool:
        return _is_set(self.tta_signing_key)

    def describe(self) -> dict[str, Any]:
        """What is configured, safe to print: secrets appear only as true or false."""
        return {
            "env": self.tta_env,
            "mode": self.tta_mode.value,
            "replay_capture": self.tta_replay_capture,
            "valio_call_budget": self.tta_valio_call_budget,
            "valio_key_set": self.has_valio_key,
            "gemini_key_set": self.has_gemini_key,
            "agent_provider": self.tta_agent_provider,
            "agent_model": self.tta_agent_model if self.has_agent_endpoint else None,
            "agent_base_url_set": bool(self.tta_agent_base_url),
            "agent_key_set": self.has_agent_key,
            "database_url_set": self.has_database_url,
            "context_dev_key_set": self.has_context_dev_key,
            "tokens_set": self.has_tokens,
            "signing_key_set": self.has_signing_key,
            "supplier_suggestions": self.tta_supplier_suggestions,
            "customer_standing_orders": self.tta_customer_standing_orders,
        }

    @classmethod
    def for_tests(cls, **overrides: Any) -> Settings:
        """Settings that read no `.env` file and carry no secret unless a test passes one. The order book starts
        empty: the demo customers' standing orders are set up at start only when a test asks for them."""
        values: dict[str, Any] = {name: None for name in _SECRET_FIELDS}
        values.update(tta_env="dev", tta_mode=DataSource.REPLAY, tta_gemini_model=None, tta_demo_clock=None,
                      tta_agent_provider=AGENT_PROVIDER_NONE, tta_agent_base_url=None, tta_agent_model=None,
                      tta_supplier_suggestions=True, tta_customer_standing_orders=False)
        values.update(overrides)
        return cls(_env_file=None, **values)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
