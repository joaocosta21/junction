"""Record price and availability responses of the Valio mock API as a replay capture.

Usage (from the repository root):
    .venv/bin/python scripts/capture_valio.py --capture 2026-11-14-demo \
        --category-prefix 104 --category-prefix 18720 --with-listed-substitutes

Writes fixtures/valio/<capture>/: the response bodies, the id list and a manifest with `timeNow`.
The API key is read from the settings and sent only as the `X-API-Key` header; it is never
written or printed. Each chunk of up to 1,000 ids costs two calls (one price, one availability).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx

from tta.config import Settings, get_settings

CHUNK_SIZE = 1000
SECONDS_BETWEEN_CALLS = 1.1
TIMEOUT_SECONDS = 60.0
# The API sits behind Cloudflare, which rejects Python's default user agent (AIMO/FINDINGS.md section 1).
USER_AGENT = "tta-gateway/0.1 (+capture)"
DEFAULT_REQUESTED_DATE = "2026-11-16"


def select_ids(settings: Settings, prefixes: list[str], ids: list[str], with_substitutes: bool) -> list[str]:
    with settings.tta_product_file.open(encoding="utf-8-sig") as handle:
        products: list[dict[str, Any]] = json.load(handle)
    by_id = {str(product["id"]): product for product in products}
    chosen = {pid for pid in ids if pid in by_id}
    if prefixes:
        wanted = tuple(prefixes)
        chosen |= {pid for pid, product in by_id.items() if str(product.get("category", "")).startswith(wanted)}
    if with_substitutes:
        for pid in list(chosen):
            for pair in by_id[pid].get("substitutions", []):
                substitute = str(pair.get("substituteProduct", ""))
                if substitute in by_id:
                    chosen.add(substitute)
    return sorted(chosen)


def post(client: httpx.Client, settings: Settings, endpoint: str, ids: list[str], requested_date: str) -> str:
    key = settings.valio_aimo_api_key.get_secret_value() if settings.valio_aimo_api_key else ""
    response = client.post(
        f"{settings.valio_aimo_base_url.rstrip('/')}/{endpoint}",
        headers={"X-API-Key": key, "Accept": "application/json", "User-Agent": USER_AGENT},
        json={"customer": settings.tta_customer, "requestedDate": requested_date, "products": ids},
    )
    if response.status_code != httpx.codes.OK:
        raise SystemExit(f"{endpoint}: HTTP {response.status_code}; nothing written for this call")
    body = response.text
    if key and key in body:
        raise SystemExit(f"{endpoint}: the response echoes the key; nothing written")
    if not isinstance(json.loads(body).get("products"), list):
        raise SystemExit(f"{endpoint}: unexpected body shape; nothing written")
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--capture", required=True, help="folder name under fixtures/valio/")
    parser.add_argument("--category-prefix", action="append", default=[], help="repeatable")
    parser.add_argument("--id", action="append", default=[], help="repeatable product id")
    parser.add_argument("--with-listed-substitutes", action="store_true")
    parser.add_argument("--requested-date", default=DEFAULT_REQUESTED_DATE)
    parser.add_argument("--max-ids", type=int, default=CHUNK_SIZE)
    args = parser.parse_args()

    settings = get_settings()
    if not settings.has_valio_key:
        raise SystemExit("VALIO_AIMO_API_KEY is not set; nothing captured")
    ids = select_ids(settings, args.category_prefix, args.id, args.with_listed_substitutes)
    if not ids or len(ids) > args.max_ids:
        raise SystemExit(f"{len(ids)} ids selected; expected between 1 and {args.max_ids}")

    target: Path = settings.valio_fixtures_dir / args.capture
    target.mkdir(parents=True, exist_ok=True)
    files: dict[str, list[str]] = {"availability": [], "price": []}
    time_nows: list[str] = []
    calls = 0
    with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
        for number, start in enumerate(range(0, len(ids), CHUNK_SIZE), start=1):
            chunk = ids[start : start + CHUNK_SIZE]
            for endpoint in ("availability", "price"):
                if calls:
                    time.sleep(SECONDS_BETWEEN_CALLS)
                body = post(client, settings, endpoint, chunk, args.requested_date)
                calls += 1
                name = f"{endpoint}-{number}.json"
                (target / name).write_text(body, encoding="utf-8")
                files[endpoint].append(name)
                if endpoint == "availability":
                    time_nows.append(json.loads(body)["timeNow"])
    manifest = {
        "capture": args.capture,
        "time_now": max(time_nows),
        "requested_date": args.requested_date,
        "customer": settings.tta_customer,
        "product_count": len(ids),
        "calls": calls,
        "files": files,
        "selection": {
            "category_prefixes": args.category_prefix,
            "ids": args.id,
            "with_listed_substitutes": args.with_listed_substitutes,
        },
    }
    (target / "ids.json").write_text(json.dumps(ids), encoding="utf-8")
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"captured {len(ids)} ids in {calls} calls -> {target.relative_to(settings.tta_fixtures_dir.parent)}")
    print(f"timeNow {manifest['time_now']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
