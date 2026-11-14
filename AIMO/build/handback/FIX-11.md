# FIX-11 — done

The tests were written first and seen failing before the code was written. Against a temporary skeleton, 30 of 45 failed. The room test failed the way the reported bug does: 12 browsers behind one address, and the buyer agent ran only 5 times. Two mutations were then tried, and the tests catch both:
- If the cookie is read on `/v1` and `/mcp` too, 8 tests fail.
- If the address cap is removed, 5 tests fail.

No call was made to Gemini, to the Valio API or to the deployed app.

## Built
- `src/tta/api/limits.py`:
  - `browser_key_of(scope)`: the own-book cookie of a page request. It reads `__Host-tta_book` first, then `tta_book`, and only a 43-character URL-safe key counts. The Cookie header is bounded to 8 KiB, and a path under `/v1` or `/mcp` is never a browser.
  - `is_page_path`, and `current_browser_key()`.
  - `as_client(key, *, browser=None)` sets both context variables.
  - `ClientKeyMiddleware` sets the browser beside the address.
  - `ADDRESS_CAPS` (60 lookups, 60 orders, 15 model calls a minute), as named constants.
  - In `CallLimits`, a demo call counts in its own window (the browser's, or the address's when there is no cookie) and in the address cap, then the ceiling.
  - New sentences `BROWSER_LIMITED` ("from this browser") and `ADDRESS_LIMITED` ("from one address for all its browsers and callers together"). `VISITOR_LIMITED` now says "from one address".
- `src/tta/api/sandbox.py`: `Sandboxes.open` counts each new book for the address of the request: `MAX_NEW_BOOKS_PER_ADDRESS = 30` per `NEW_BOOKS_WINDOW_MINUTES = 10`. Above that it raises `RateLimited` with "Too many new demo order books from one address: at most 30 in 10 minutes …" and `Retry-After`. It builds nothing and drops no other book. The pages already show a `TtaError` as a 429 page.
- `tests/api/test_room_limits.py` (new, 37 tests): cookie and path rules, the middleware, browser windows, the address cap per kind under cookie rotation, no cookie means the address, the ceiling still holds, environment tokens still count by identity, and the new-book cap.
- `tests/api/test_room_pages.py` (new, 5 tests, through the real pages with a scenario-2 runner and no model):
  - Twelve browsers on one address all run scenario 2 with the agent.
  - The 61st lookup is refused with the address sentence, on the pages and over REST. Another address is still served.
  - Over HTTPS, the 6th run of one browser says "from this browser" and its neighbour still runs.
  - Page runs without the book cookie are counted by address, as before.
  - REST carrying the cookie is counted by address.
  - The 31st rotated cookie gets a 429 page.
- `tests/api/test_visitors.py`: two assertions changed from "one visitor" to "from one address:", because this task changes the sentence on purpose.

## Tests
`COVERAGE_FILE=/private/tmp/claude-501/-Users-joaocosta-Pessoal-junction/438d0f7d-7f46-4faf-8c0f-07ba7c612213/scratchpad/fix11/.coverage`, with `-p no:cacheprovider`.
```
.venv/bin/python -m pytest tests/api -q --cov=tta.api.limits --cov=tta.api.sandbox --cov-report=term-missing
src/tta/api/limits.py      234      1     50      0    99%   177
src/tta/api/sandbox.py      92      0     18      1    99%   128->exit
TOTAL                      326      1     68      1    99%
345 passed in 43.55s

.venv/bin/python -m pytest tests/ui -q     -> 192 passed in 17.41s
.venv/bin/python -m pytest tests/mcp -q    -> 59 passed in 12.04s
.venv/bin/python -m pytest tests/e2e -q    -> 16 passed in 4.80s

.venv/bin/ruff check src/tta/api/limits.py src/tta/api/sandbox.py tests/api/test_room_limits.py tests/api/test_room_pages.py tests/api/test_visitors.py tests/api/test_limits.py
All checks passed!
```
The two lines not covered (`RateLimiter.allows` and the `drop` branch) are older code that this task did not change.

## Assumptions
- I read "live supplier looks unchanged" literally: they are still keyed on the address, because `fallback.py` reads `current_client_key()` and that is still the address. A room therefore shares 2 live looks a minute. Above that, the capture answers, labelled replay. This only matters in live mode.
- The address cap counts every demo call from the address: pages, REST and MCP together.
- The address cap applies only in dev and demo (`per_visitor`). Environment tokens outside dev and demo are still counted by identity alone.
- A page request is any path outside `/v1…` and `/mcp…`, the same split as `_PagesMount`.
- A well-formed cookie that the pages never issued cannot be told apart from a real one and counts as a browser. The address cap bounds it.
- A browser's window is keyed on the cookie alone, so it follows the browser across addresses.
- A page POST without a book cookie is counted by address, even though `BookCookie` makes a key for it during that same request.
- A new book is counted when it is built, before the call limits are checked. "Start again" followed by a run counts as one new book. The blank read-only book is not counted.
- When two windows are full with the same wait, the refusal names the caller's own window: the browser's, or the address's when there is no cookie.
- Callers with no peer address (`unknown`) share one address cap and one new-book counter, as they already shared one window.

## Contract changes needed
None.

## Not done
- **Live check.** It needs the deployed app, which this task may not call.
  - Open the deployed `/` from one network in two private windows.
  - Click scenario 2 six times in one of them within a minute. The 6th run should say "The buyer agent could not run: Too many request readings and agent runs from this browser…".
  - Click scenario 2 in the other window. The agent should still run.
- **Files I do not own still describe the old rule.**
  - `src/tta/api/docs.py`, about lines 88–96: "a caller is one visitor, its address". This should say: per browser on the pages, per address for REST and MCP; per address 60/60/15 a minute; 30 new books per 10 minutes.
  - `docs/DEMO.md`, lines 31, 33 and 134: "Everyone behind one network address … shares these windows", and the troubleshooting line for "Too many requests".
  - `docs/ASSUMPTIONS.md`.
  - `tests/api/test_sandbox.py:105`: the comment "a new browser does not buy a new window" is now true only for calls made without a browser in the context. The test still passes.
- **`limits.py` is 433 lines**, over the 400-line rule; it was 362 before this task. Moving `BodyLimitMiddleware`, `_declared_length` and their constants into their own module (about 45 lines) would fix this. That needs a new file and a change to the import in `app.py`, and I own neither.
- **Risks from the decided values** (no code was changed for them):
  - More than 30 new browsers behind one NAT within 10 minutes: the 31st gets a 429 page for up to 10 minutes.
  - More than 15 agent runs a minute from one address: the 16th example runs from its typed request, with the "could not run" note.
  - One address can still cycle all 300 books in 100 minutes (30 every 10 minutes). That pushes out only books that nobody has used for about that long, which is less than the 2-hour idle limit. Books in use are touched on every request and stay.

## Questions written
0. This task answers question 1 of `AIMO/build/questions/FIX-10.md`.
