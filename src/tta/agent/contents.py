"""The conversation of a run, as `generateContent` takes it (SPEC section 11; task T10).

The runner keeps its history as plain steps (`tta.agent.model.TurnCall.history`): the buyer's request
(`user_input`), what the model returned (`model_content`, written here) and the gateway's answer to each call
(`function_result`). This module turns them into the `contents` of a `generateContent` request, following the
Gemini documentation as read on 14 Nov 2026 ("Function calling (generateContent)", "Thought signatures
(generateContent)"):
- the model's turn goes back as the `Content` it was received in, every part unchanged: a part may carry a
  thought signature, and a function call whose signature is missing is refused with a 400;
- each result names the function and the `id` of the call it answers, when the model gave the call one;
- the results of one turn go back together, in one `user` content, in the order of the calls;
- a result is `{"output": ...}`, or `{"error": ...}` for a call the gateway or the runner refused (the
  `FunctionResponse.response` convention of the SDK and the API reference).
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Any

from google.genai import types

from tta.contracts.common import JsonDict

USER_INPUT = "user_input"
MODEL_CONTENT = "model_content"
FUNCTION_RESULT = "function_result"
USER_ROLE = "user"
OUTPUT_KEY, ERROR_KEY = "output", "error"


def model_step(content: types.Content) -> JsonDict:
    """The model's turn as a history step: the `Content` in its JSON form, signatures as base64 text."""
    return {"type": MODEL_CONTENT, "content": content.model_dump(mode="json", exclude_none=True)}


def _texts(items: Iterable[Any]) -> list[str]:
    return [str(item["text"]) for item in items if isinstance(item, dict) and isinstance(item.get("text"), str)]


def _model_content(step: JsonDict) -> types.Content:
    # Read back from JSON, so a signature's base64 text becomes the same bytes it was received as.
    return types.Content.model_validate_json(json.dumps(step["content"]))


def _call_ids(contents: Iterable[types.Content]) -> set[str]:
    """The ids the model gave its calls. A call it gave none is named by the runner, and that name stays here."""
    return {
        part.function_call.id
        for content in contents
        for part in content.parts or ()
        if part.function_call is not None and part.function_call.id
    }


def _result_value(step: JsonDict) -> Any:
    """The gateway's answer as the runner wrote it: the JSON text of a summary, read back into an object."""
    text = "".join(_texts(step.get("result") or ()))
    try:
        return json.loads(text)
    except ValueError:
        return text


def _function_response(step: JsonDict, model_ids: set[str]) -> types.Part:
    call_id = step.get("call_id")
    key = ERROR_KEY if step.get("is_error") else OUTPUT_KEY
    return types.Part(function_response=types.FunctionResponse(
        id=call_id if call_id in model_ids else None, name=str(step["name"]), response={key: _result_value(step)},
    ))


def _user_content(step: JsonDict) -> types.Content:
    return types.Content(role=USER_ROLE, parts=[types.Part(text=text) for text in _texts(step["content"])])


def to_contents(history: Sequence[JsonDict]) -> list[types.Content]:
    """The `contents` of a request. Raises `ValueError` for a step this module does not know: a fault of ours."""
    models = {index: _model_content(step) for index, step in enumerate(history) if step.get("type") == MODEL_CONTENT}
    model_ids = _call_ids(models.values())
    contents: list[types.Content] = []
    results: list[types.Part] = []
    for index, step in enumerate(history):
        kind = step.get("type")
        if kind == FUNCTION_RESULT:
            results.append(_function_response(step, model_ids))
            continue
        if results:
            contents.append(types.Content(role=USER_ROLE, parts=results))
            results = []
        if kind == USER_INPUT:
            contents.append(_user_content(step))
        elif kind == MODEL_CONTENT:
            contents.append(models[index])
        else:
            raise ValueError(f"A history step of type {str(kind)[:40]!r} cannot be sent to Gemini.")
    if results:
        contents.append(types.Content(role=USER_ROLE, parts=results))
    return contents


def function_tool(declarations: Sequence[JsonDict]) -> types.Tool:
    """The gateway's functions as one tool, declared as the documentation's Python examples do: `parameters` in
    the OpenAPI subset, which the SDK sends as the API's `Schema`. A function with no parameters has none."""
    return types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name=str(declaration["name"]), description=str(declaration["description"]),
            parameters=declaration.get("parameters"),
        )
        for declaration in declarations
    ])
