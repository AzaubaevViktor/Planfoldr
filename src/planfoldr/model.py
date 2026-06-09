"""Model (level 5a) and the model-agnostic action protocol.

The model is a replaceable executor inside a cycle: it generates text, emits a structured action,
and reports token usage + duration. It does NOT manage the flow, does not pick itself, does not
see other cycles' memory, and does not read its own score (scores live in the Score System; the
runtime selects via `ModelRegistry.select`).

Reuses the proven streaming + provider token-counting approach from v1
(`v1/src/planfoldr/executors.py` OllamaModelAdapter), adapted to a single-action JSON envelope so
the cycle is model-agnostic instead of depending on a provider-specific tool-call token.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional

ProgressCallback = Callable[[str, Dict[str, Any]], None]

OLLAMA_ENDPOINT = "http://127.0.0.1:11434/api/chat"


@dataclass
class ModelConfig:
    id: str
    provider: str = "stub"          # stub | ollama | openai | anthropic
    parameter_count: float = 1e9
    cost_per_token: float = 0.0
    max_tokens_per_ticket: int = 50_000
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "provider": self.provider, "parameter_count": self.parameter_count,
            "cost_per_token": self.cost_per_token, "max_tokens_per_ticket": self.max_tokens_per_ticket,
        }


@dataclass
class ModelResponse:
    content: str
    thinking: str = ""
    prompt_tokens: int = 0
    generated_tokens: int = 0
    duration_seconds: float = 0.0
    available: bool = True
    raw: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return int(self.prompt_tokens) + int(self.generated_tokens)


# --------------------------------------------------------------------------- #
# Action protocol
# --------------------------------------------------------------------------- #
@dataclass
class Action:
    action: str
    args: Dict[str, Any] = field(default_factory=dict)
    thinking: str = ""
    raw: str = ""
    error: Optional[str] = None


def parse_action(text: str) -> Action:
    """Parse a model reply into a single action. JSON-first (whole text, then an embedded object),
    with a `<tool_call>` fallback so a range of local models can drive the cycle."""
    text = (text or "").strip()
    obj = _try_json(text)
    if obj is None:
        obj = _extract_json_object(text)
    if obj is None:
        obj = _parse_tool_call(text)
    if not isinstance(obj, dict):
        return Action(action="", raw=text, error="no JSON action object found")
    function = obj.get("function") if isinstance(obj.get("function"), dict) else {}
    action = obj.get("action") or obj.get("tool") or obj.get("name") or function.get("name")
    args = obj.get("args")
    if args is None:
        args = obj.get("arguments", obj.get("parameters", function.get("arguments", {})))
    if isinstance(args, str):
        args = _try_json(args) or {"value": args}
    thinking = obj.get("thinking", "") or ""
    if not action:
        return Action(action="", args=obj if isinstance(obj, dict) else {}, thinking=thinking,
                      raw=text, error="missing 'action' field")
    return Action(
        action=str(action).strip(),
        args=args if isinstance(args, dict) else {"value": args},
        thinking=thinking, raw=text,
    )


def _try_json(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Find the first balanced {...} object in free-form text (quote/escape aware)."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = _try_json(text[start:i + 1])
                        if isinstance(candidate, dict):
                            return candidate
                        break
        start = text.find("{", start + 1)
    return None


def _parse_tool_call(text: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"<tool_call>\s*(.*?)\s*</tool_call>", text, flags=re.DOTALL)
    if match is None:
        return None
    return _try_json(match.group(1).strip())


# --------------------------------------------------------------------------- #
# Adapters
# --------------------------------------------------------------------------- #
class ModelAdapter:
    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        fmt: Optional[str] = None,
        progress: Optional[ProgressCallback] = None,
    ) -> ModelResponse:
        raise NotImplementedError


class StubModel(ModelAdapter):
    """Deterministic adapter. `script` is a list of replies (str or dict) returned in order, or a
    callable(messages) -> reply. Drives the whole orchestration in tests without a real model."""

    def __init__(self, script: Any, *, parameter_count: float = 1e9) -> None:
        self._script = script
        self._i = 0
        self.calls: List[List[Dict[str, str]]] = []
        self.parameter_count = parameter_count

    def generate(self, messages, *, fmt=None, progress=None) -> ModelResponse:
        self.calls.append(list(messages))
        if callable(self._script):
            reply = self._script(messages)
        elif isinstance(self._script, list):
            reply = self._script[min(self._i, len(self._script) - 1)]
            self._i += 1
        else:
            reply = self._script
        content = reply if isinstance(reply, str) else json.dumps(reply)
        if progress is not None:
            progress("model_stream_chunk", {"kind": "content", "text": content})
        gen = max(1, len(content) // 4)
        prompt = sum(len(m.get("content", "")) for m in messages) // 4
        return ModelResponse(content=content, prompt_tokens=prompt, generated_tokens=gen,
                             duration_seconds=0.0, raw=content, metadata={"adapter": "stub"})


class OllamaModel(ModelAdapter):
    def __init__(self, model: str, *, endpoint: str = OLLAMA_ENDPOINT, timeout: float = 600.0,
                 options: Optional[Dict[str, Any]] = None) -> None:
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self.options = dict(options or {})

    def generate(self, messages, *, fmt=None, progress=None) -> ModelResponse:
        payload: Dict[str, Any] = {"model": self.model, "messages": list(messages), "stream": True}
        if fmt:
            payload["format"] = fmt
        if self.options:
            payload["options"] = self.options
        request = urllib.request.Request(
            self.endpoint, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        content_parts: List[str] = []
        thinking_parts: List[str] = []
        prompt_tokens = 0
        generated_tokens = 0
        provider_seconds = 0.0
        started = time.time()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    chunk = json.loads(line)
                    message = chunk.get("message", {})
                    thinking = message.get("thinking", "")
                    content = message.get("content", "")
                    if thinking:
                        thinking_parts.append(thinking)
                        _emit(progress, "model_stream_chunk", kind="thinking", text=thinking)
                    if content:
                        content_parts.append(content)
                        _emit(progress, "model_stream_chunk", kind="content", text=content)
                    if chunk.get("done"):
                        prompt_tokens = int(chunk.get("prompt_eval_count") or 0)
                        generated_tokens = int(chunk.get("eval_count") or 0)
                        provider_seconds = float(chunk.get("total_duration") or 0) / 1e9
                        break
        except (OSError, urllib.error.URLError) as exc:
            _emit(progress, "model_stream_error", reason=str(exc))
            return ModelResponse(content="", available=False, raw=str(exc),
                                 metadata={"adapter": "ollama", "error": str(exc)})
        wall = time.time() - started
        content = "".join(content_parts)
        if generated_tokens == 0:
            generated_tokens = max(1, len(content) // 4)
        return ModelResponse(
            content=content, thinking="".join(thinking_parts),
            prompt_tokens=prompt_tokens, generated_tokens=generated_tokens,
            duration_seconds=provider_seconds or wall, raw=content,
            metadata={"adapter": "ollama", "model": self.model, "wall_seconds": wall},
        )


def _emit(progress: Optional[ProgressCallback], event: str, **fields: Any) -> None:
    if progress is not None:
        progress(event, fields)


# --------------------------------------------------------------------------- #
# Registry + runtime selection
# --------------------------------------------------------------------------- #
class ModelRegistry:
    """Available models; the runtime selects via the Score System -- the model never selects
    itself."""

    def __init__(self) -> None:
        self.configs: Dict[str, ModelConfig] = {}
        self.adapters: Dict[str, ModelAdapter] = {}

    def register(self, config: ModelConfig, adapter: ModelAdapter) -> None:
        self.configs[config.id] = config
        self.adapters[config.id] = adapter

    def candidates(self) -> List[str]:
        return list(self.configs)

    def adapter_for(self, model_id: str) -> ModelAdapter:
        return self.adapters[model_id]

    def config_for(self, model_id: str) -> ModelConfig:
        return self.configs[model_id]

    def select(self, role: str, task_type: str, score_system: Any) -> Optional[ModelConfig]:
        for model_id, cfg in self.configs.items():
            score_system.register_model(model_id, cfg.parameter_count)
        best = score_system.best_model(role, task_type, self.candidates())
        return self.configs.get(best) if best else None
