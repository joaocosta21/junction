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
)


def _is_set(secret: SecretStr | None) -> bool:
    return bool(secret is not None and secret.get_secret_value().strip())


class Settings(BaseSettings):
    """Read once from the environment and, when present, the repository's `.env`."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore", frozen=True
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
            "database_url_set": self.has_database_url,
            "context_dev_key_set": self.has_context_dev_key,
            "tokens_set": self.has_tokens,
            "signing_key_set": self.has_signing_key,
        }

    @classmethod
    def for_tests(cls, **overrides: Any) -> Settings:
        """Settings that read no `.env` file and carry no secret unless a test passes one."""
        values: dict[str, Any] = {name: None for name in _SECRET_FIELDS}
        values.update(tta_env="dev", tta_mode=DataSource.REPLAY, tta_gemini_model=None, tta_demo_clock=None)
        values.update(overrides)
        return cls(_env_file=None, **values)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
