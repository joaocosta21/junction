# T14 — Deployment on Modal

**Scores on:** 30% (a link a judge can open) · 15% (path to production) · the Modal award.
**Needs:** T13. **Owns:** `deploy/`, `docs/DEPLOY.md`.
**Read first:** `MODAL-CHALLENGE.md` · **the current Modal documentation** (ASGI web endpoints, images, secrets, volumes, container limits). Do not rely on memory for decorator or parameter names.

## Build
- `deploy/modal_app.py`: an image with the package, the product file and the fixtures; the FastAPI app served as an ASGI endpoint; one container at a time (SQLite); a Volume for `var/`; `TTA_ENV=demo`.
- **Secrets:** only the values the app uses reach Modal — `VALIO_AIMO_API_KEY`, `VALIO_AIMO_BASE_URL`, `GEMINI_API_KEY` — read from the local environment at deploy time and attached as a Modal Secret (check the current documentation for the way to build a secret from local values). If S1 or S2 were built and the start line names them, `DATABASE_URL` and `CONTEXT_DEV_API_KEY` as well. Never the whole `.env` (it also holds a portal password). No value in a command line, in the image, in a repository file or in any output you produce.
- Mode: live, falling back to replay with a visible label when the mock cannot be reached or the call budget is spent.
- The public demo accepts only the demo identities; live lookups are rate-limited and cached; the page says that orders are recorded in our order book and commit nobody.
- `docs/DEPLOY.md`: deploy, check, roll back, and what the Modal award write-up can honestly claim (hosting, secrets, volume; not GPU work).

## Deploying
- Only if `modal` is authenticated **and** the orchestrator's prompt to you says the human approved the deployment. Then deploy once, open `/healthz` and `/`, run scenario 2 by HTTP, and put the URL in the hand-back.
- Otherwise do not deploy: finish the files, mark "partly done: not deployed", and give the three commands the human runs.
