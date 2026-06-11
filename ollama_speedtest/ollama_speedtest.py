#!/usr/bin/env python3
"""Benchmark local Ollama models across meaningful project-context prompt sizes.

The script is intentionally standalone: it only uses the Python standard library, discovers
current models from Ollama, builds prompts from this repository, and persists terminal results
incrementally so a restart continues where the previous run stopped.
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator


DEFAULT_SIZES = [100, 1_000, 2_500, 5_000, 10_000, 20_000, 40_000, 80_000]
DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
STATE_VERSION = 1
TERMINAL_STATUSES = {"ok", "skipped", "error"}
CONTEXT_ERROR_RE = re.compile(
    r"context|num_ctx|maximum context|prompt.*too long|exceed(?:ed|s)?", re.IGNORECASE
)


@dataclass
class ModelInfo:
    name: str
    parameter_size: str = ""
    parameter_count_b: float | None = None
    context_window: int | None = None


@dataclass
class ProbeResult:
    model: str
    size_chars: int
    status: str
    prompt_variant: str
    prompt_chars: int
    estimated_prompt_tokens: int
    required_context_tokens: int
    context_window: int | None
    first_token_seconds: float | None = None
    generation_tokens_per_second: float | None = None
    prompt_eval_tokens_per_second: float | None = None
    prompt_eval_seconds: float | None = None
    generation_chars_per_second: float | None = None
    warmup_seconds: float | None = None
    warmup_rss_peak_gb: float | None = None
    warmup_rss_avg_gb: float | None = None
    ollama_rss_peak_gb: float | None = None
    ollama_rss_avg_gb: float | None = None
    generated_tokens: int = 0
    generated_chars: int = 0
    prompt_tokens: int = 0
    wall_seconds: float = 0.0
    error: str = ""
    skipped_reason: str = ""


class OllamaError(RuntimeError):
    def __init__(self, message: str, *, context_related: bool = False) -> None:
        super().__init__(message)
        self.context_related = context_related


class ProcessMemoryMonitor:
    def __init__(self, process_names: tuple[str, ...] = ("ollama-server", "llama-server"), interval_seconds: float = 0.25) -> None:
        self.process_names = process_names
        self.interval_seconds = interval_seconds
        self.samples_gb: list[float] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        first = sample_process_rss_gb(self.process_names)
        if first is not None:
            self.samples_gb.append(first)
        self._thread = threading.Thread(target=self._run, name="ollama-memory-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> dict[str, float | None]:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.interval_seconds * 4))
        last = sample_process_rss_gb(self.process_names)
        if last is not None:
            self.samples_gb.append(last)
        if not self.samples_gb:
            return {"ollama_rss_peak_gb": None, "ollama_rss_avg_gb": None}
        return {
            "ollama_rss_peak_gb": round(max(self.samples_gb), 2),
            "ollama_rss_avg_gb": round(sum(self.samples_gb) / len(self.samples_gb), 2),
        }

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            value = sample_process_rss_gb(self.process_names)
            if value is not None:
                self.samples_gb.append(value)


def sample_process_rss_gb(process_names: tuple[str, ...] | str) -> float | None:
    if isinstance(process_names, str):
        names = (process_names,)
    else:
        names = process_names
    try:
        proc = subprocess.run(
            ["ps", "-wwaxo", "pid=,rss=,args="],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    total_kib = 0
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            _pid_text, rss_text, args = stripped.split(None, 2)
            rss_kib = int(rss_text)
        except ValueError:
            continue
        if any(name in args for name in names):
            total_kib += rss_kib
    return round(total_kib / (1024 * 1024), 4) if total_kib else None


class OllamaClient:
    def __init__(self, endpoint: str, timeout: float) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.timeout = timeout

    def list_models(self) -> list[dict[str, Any]]:
        data = self._json("GET", "/api/tags")
        return list(data.get("models") or [])

    def show_model(self, model: str) -> dict[str, Any]:
        return self._json("POST", "/api/show", {"model": model})

    def chat_stream(
        self,
        *,
        model: str,
        prompt: str,
        num_predict: int,
        required_context_tokens: int,
        context_window: int | None,
        stream_callback: Any | None = None,
    ) -> dict[str, Any]:
        options: dict[str, Any] = {
            "temperature": 0,
            "num_predict": num_predict,
        }
        if required_context_tokens > 0:
            options["num_ctx"] = min(required_context_tokens, context_window) if context_window else required_context_tokens
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "options": options,
        }
        request = urllib.request.Request(
            self.endpoint + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        first_token_seconds: float | None = None
        final: dict[str, Any] = {}
        generated_chars = 0

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if chunk.get("error"):
                        message = str(chunk.get("error"))
                        raise OllamaError(message, context_related=is_context_error(message))
                    message = chunk.get("message") or {}
                    content = message.get("content") or ""
                    thinking = message.get("thinking") or ""
                    produced = content + thinking
                    if produced and first_token_seconds is None:
                        first_token_seconds = time.perf_counter() - started
                    generated_chars += len(produced)
                    if stream_callback is not None:
                        if thinking:
                            stream_callback({"event": "stream_chunk", "kind": "thinking", "text": thinking})
                        if content:
                            stream_callback({"event": "stream_chunk", "kind": "content", "text": content})
                    if chunk.get("done"):
                        final = chunk
                        if stream_callback is not None:
                            stream_callback({"event": "stream_done", "raw": summarize_done_chunk(chunk)})
                        break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            message = body or str(exc)
            raise OllamaError(message, context_related=is_context_error(message)) from exc
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            message = str(exc)
            raise OllamaError(message, context_related=is_context_error(message)) from exc

        wall = time.perf_counter() - started
        eval_count = int(final.get("eval_count") or max(1, generated_chars // 4))
        prompt_eval_count = int(final.get("prompt_eval_count") or 0)
        eval_duration = int(final.get("eval_duration") or 0) / 1_000_000_000
        prompt_eval_duration = int(final.get("prompt_eval_duration") or 0) / 1_000_000_000
        if eval_duration <= 0 and first_token_seconds is not None:
            eval_duration = max(0.001, wall - first_token_seconds)
        chars_duration = eval_duration
        return {
            "first_token_seconds": first_token_seconds,
            "generation_tokens_per_second": round(eval_count / eval_duration, 2) if eval_duration > 0 else None,
            "generation_chars_per_second": (
                round(generated_chars / chars_duration, 2) if chars_duration > 0 else None
            ),
            "prompt_eval_tokens_per_second": (
                round(prompt_eval_count / prompt_eval_duration, 2) if prompt_eval_count and prompt_eval_duration > 0 else None
            ),
            "prompt_eval_seconds": round(prompt_eval_duration, 6) if prompt_eval_duration > 0 else None,
            "generated_tokens": eval_count,
            "generated_chars": generated_chars,
            "prompt_tokens": prompt_eval_count,
            "wall_seconds": round(wall, 3),
        }

    def _json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint + path,
            data=data,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))


def project_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def discover_context_files(root: Path) -> list[Path]:
    root_md = sorted(p for p in root.glob("*.md") if p.is_file())
    src_py = sorted(p for p in (root / "src").rglob("*.py") if p.is_file())
    return root_md + src_py


def build_prompt(root: Path, target_chars: int, *, variant: str = "") -> str:
    prefix = ""
    if variant:
        prefix += f"{stable_digest(variant)[:16]} benchmark sample id.\n"
    prefix += "You are architector. You need to invent next steps for this project:\n\n"
    remaining = max(0, target_chars - len(prefix))
    parts = [prefix.rstrip()]

    for path in order_context_files(root, variant):
        if remaining <= 0:
            break
        rel = path.relative_to(root).as_posix()
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        header = f"\n\n{rel}:\n```\n"
        footer = "\n```"
        overhead = len(header) + len(footer)
        if remaining <= overhead:
            break
        take = max(0, remaining - overhead)
        chunk_variant = f"{variant}:{rel}" if variant else ""
        chunk = content_slice(content, take, chunk_variant)
        if not chunk:
            continue
        parts.append(header + chunk.rstrip() + footer)
        remaining = target_chars - len("".join(parts))

    prompt = "".join(parts)
    if len(prompt) < target_chars:
        prompt += "\n\nReturn a concise, prioritized implementation plan with risks and verification steps."
    return prompt


def order_context_files(root: Path, variant: str) -> list[Path]:
    files = discover_context_files(root)
    root_md = [p for p in files if p.parent == root and p.suffix == ".md"]
    src_py = [p for p in files if p.suffix == ".py" and root / "src" in p.parents]
    md_variant = f"{variant}:md" if variant else ""
    py_variant = f"{variant}:py" if variant else ""
    return rotate_files(root_md, md_variant) + rotate_files(src_py, py_variant)


def rotate_files(paths: list[Path], variant: str) -> list[Path]:
    if len(paths) <= 1 or not variant:
        return paths
    offset = stable_int(variant) % len(paths)
    rotated = paths[offset:] + paths[:offset]
    if stable_int(variant + ":reverse") % 2:
        rotated = list(reversed(rotated))
    return rotated


def content_slice(content: str, take: int, variant: str) -> str:
    if take >= len(content):
        return content
    if take <= 0:
        return ""
    if not variant:
        return content[:take]
    start = stable_int(variant) % max(1, len(content) - take)
    return content[start : start + take]


def stable_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def stable_int(text: str) -> int:
    return int(stable_digest(text)[:16], 16)


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def model_info_from_tags(tag: dict[str, Any], show: dict[str, Any] | None = None) -> ModelInfo:
    details = tag.get("details") or {}
    parameter_size = str(details.get("parameter_size") or "")
    name = str(tag.get("name") or tag.get("model") or "")
    return ModelInfo(
        name=name,
        parameter_size=parameter_size,
        parameter_count_b=parse_parameter_size_b(parameter_size),
        context_window=extract_context_window(show or {}),
    )


def parse_parameter_size_b(text: str) -> float | None:
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*([bmk])", text or "", flags=re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit == "b":
        return value
    if unit == "m":
        return value / 1_000
    if unit == "k":
        return value / 1_000_000
    return None


def parse_size_limit_b(text: str | None) -> float | None:
    if not text:
        return None
    parsed = parse_parameter_size_b(text)
    if parsed is not None:
        return parsed
    return float(text)


def extract_context_window(show: dict[str, Any]) -> int | None:
    candidates: list[int] = []
    model_info = show.get("model_info") or {}
    if isinstance(model_info, dict):
        for key, value in model_info.items():
            if "context_length" in str(key) or "context_window" in str(key):
                try:
                    candidates.append(int(value))
                except (TypeError, ValueError):
                    pass
    parameters = show.get("parameters")
    if isinstance(parameters, str):
        for match in re.finditer(r"(?:num_ctx|context_length)\s+([0-9]+)", parameters):
            candidates.append(int(match.group(1)))
    return max(candidates) if candidates else None


def is_context_error(message: str) -> bool:
    return bool(CONTEXT_ERROR_RE.search(message or ""))


def summarize_done_chunk(chunk: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "done",
        "total_duration",
        "load_duration",
        "prompt_eval_count",
        "prompt_eval_duration",
        "eval_count",
        "eval_duration",
    ]
    return {key: chunk.get(key) for key in keys if key in chunk}


def load_state(path: Path) -> dict[str, Any]:
    if path.suffix == ".jsonl":
        return load_jsonl_state(path)
    if not path.exists():
        return {"version": STATE_VERSION, "entries": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        backup = path.with_suffix(path.suffix + f".broken-{int(time.time())}")
        try:
            path.rename(backup)
        except OSError:
            pass
        return {"version": STATE_VERSION, "entries": {}}
    if not isinstance(state, dict):
        return {"version": STATE_VERSION, "entries": {}}
    state.setdefault("version", STATE_VERSION)
    state.setdefault("entries", {})
    return state


def load_jsonl_state(path: Path) -> dict[str, Any]:
    state: dict[str, Any] = {"version": STATE_VERSION, "entries": {}}
    if not path.exists():
        return state
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return state
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        if isinstance(record.get("entries"), dict):
            state["entries"].update(record["entries"])
            state["updated_at"] = record.get("updated_at", state.get("updated_at"))
            continue
        key = record.get("key")
        entry = record.get("entry")
        if isinstance(key, str) and isinstance(entry, dict):
            state["entries"][key] = entry
            state["updated_at"] = record.get("updated_at", state.get("updated_at"))
            continue
        model = record.get("model")
        size = record.get("size_chars")
        if model is not None and size is not None:
            state["entries"][entry_key(str(model), int(size))] = record
    return state


def save_state(path: Path, state: dict[str, Any], changed_key: str | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    if path.suffix == ".jsonl":
        record: dict[str, Any] = {
            "version": state.get("version", STATE_VERSION),
            "updated_at": state["updated_at"],
        }
        if changed_key is not None and changed_key in state.get("entries", {}):
            record["key"] = changed_key
            record["entry"] = state["entries"][changed_key]
        else:
            record["event"] = "state_checkpoint"
            record["entry_count"] = len(state.get("entries", {}))
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
        return
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")


def new_run_log_path(root: Path) -> Path:
    stamp = time.strftime("%Y-%m-%d-%H-%M-%S")
    return root / "ollama_speedtest" / "run" / f"{stamp}-{uuid.uuid4().hex[:8]}.jsonl"


def write_run_event(path: Path | None, event: dict[str, Any]) -> None:
    if path is None:
        return
    record = dict(event)
    record.setdefault("at", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    append_jsonl(path, record)


def write_report(path: Path, records: Iterable[dict[str, Any]]) -> None:
    rows = sorted(records, key=lambda r: (str(r.get("model", "")), int(r.get("size_chars", 0))))
    lines = [
        "# Ollama Speedtest Report",
        "",
        f"Updated: {time.strftime('%Y-%m-%d %H:%M:%S %z')}",
        "",
        "| model | chars | prompt tokens | warmup s | prompt eval s | first token s | gen tok/s | gen chars/s | prompt tok/s | rss peak GB | rss avg GB | status | reason |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        reason = row.get("skipped_reason") or row.get("error") or ""
        lines.append(
            "| {model} | {size} | {prompt_tokens} | {warmup} | {prompt_eval_seconds} | {first} | {gen} | {gen_chars} | {prompt_speed} | {rss_peak} | {rss_avg} | {status} | {reason} |".format(
                model=escape_md(str(row.get("model", ""))),
                size=int(row.get("size_chars", 0)),
                prompt_tokens=fmt(row.get("prompt_tokens") or row.get("estimated_prompt_tokens")),
                warmup=fmt(row.get("warmup_seconds")),
                prompt_eval_seconds=fmt(row.get("prompt_eval_seconds")),
                status=escape_md(str(row.get("status", ""))),
                first=fmt(row.get("first_token_seconds")),
                gen=fmt(row.get("generation_tokens_per_second")),
                gen_chars=fmt(row.get("generation_chars_per_second")),
                prompt_speed=fmt(row.get("prompt_eval_tokens_per_second")),
                rss_peak=fmt(memory_gb(row, "ollama_rss_peak")),
                rss_avg=fmt(memory_gb(row, "ollama_rss_avg")),
                reason=escape_md(str(reason).replace("\n", " ")[:120]),
            )
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def escape_md(text: str) -> str:
    return text.replace("|", "\\|")


def fmt(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def memory_gb(row: dict[str, Any], prefix: str) -> float | None:
    gb = row.get(f"{prefix}_gb")
    if gb is not None:
        return float(gb)
    mib = row.get(f"{prefix}_mib")
    if mib is not None:
        return round(float(mib) / 1024, 2)
    return None


def entry_key(model: str, size: int) -> str:
    return f"{model}::{size}"


def should_skip_existing(entry: dict[str, Any] | None, *, rerun: bool, retry_errors: bool) -> bool:
    if not entry or rerun:
        return False
    status = entry.get("status")
    if status == "error" and retry_errors:
        return False
    return status in TERMINAL_STATUSES


def select_models(
    models: list[ModelInfo],
    *,
    patterns: list[str],
    max_parameter_size_b: float | None,
) -> list[ModelInfo]:
    selected: list[ModelInfo] = []
    for model in models:
        if patterns and not any(fnmatch.fnmatch(model.name, pattern) for pattern in patterns):
            continue
        if max_parameter_size_b is not None:
            if model.parameter_count_b is None or model.parameter_count_b >= max_parameter_size_b:
                continue
        selected.append(model)
    return selected


def run_probe(
    *,
    client: OllamaClient,
    model: ModelInfo,
    root: Path,
    size: int,
    num_predict: int,
    prompt_variant: str = "",
    warmup_metrics: dict[str, float | None] | None = None,
    run_log: Path | None = None,
) -> ProbeResult:
    prompt = build_prompt(root, size, variant=prompt_variant)
    prompt_tokens_estimate = estimate_tokens(prompt)
    required_context_tokens = prompt_tokens_estimate + num_predict + 64
    write_run_event(
        run_log,
        {
            "event": "prompt",
            "model": model.name,
            "size_chars": size,
            "prompt_variant": prompt_variant,
            "prompt_chars": len(prompt),
            "estimated_prompt_tokens": prompt_tokens_estimate,
            "prompt": prompt,
        },
    )
    warmup_metrics = warmup_metrics or {}
    if model.context_window is not None and required_context_tokens > model.context_window:
        return ProbeResult(
            model=model.name,
            size_chars=size,
            status="skipped",
            prompt_variant=prompt_variant,
            prompt_chars=len(prompt),
            estimated_prompt_tokens=prompt_tokens_estimate,
            required_context_tokens=required_context_tokens,
            context_window=model.context_window,
            warmup_seconds=warmup_metrics.get("warmup_seconds"),
            warmup_rss_peak_gb=warmup_metrics.get("warmup_rss_peak_gb"),
            warmup_rss_avg_gb=warmup_metrics.get("warmup_rss_avg_gb"),
            skipped_reason=(
                f"estimated prompt requires {required_context_tokens} context tokens; "
                f"model advertises {model.context_window}"
            ),
        )

    started = time.perf_counter()
    monitor = ProcessMemoryMonitor()
    monitor.start()
    try:
        metrics = client.chat_stream(
            model=model.name,
            prompt=prompt,
            num_predict=num_predict,
            required_context_tokens=required_context_tokens,
            context_window=model.context_window,
            stream_callback=lambda event: write_run_event(
                run_log,
                {
                    **event,
                    "model": model.name,
                    "size_chars": size,
                    "prompt_variant": prompt_variant,
                },
            ),
        )
    except OllamaError as exc:
        memory_metrics = monitor.stop()
        status = "skipped" if exc.context_related else "error"
        return ProbeResult(
            model=model.name,
            size_chars=size,
            status=status,
            prompt_variant=prompt_variant,
            prompt_chars=len(prompt),
            estimated_prompt_tokens=prompt_tokens_estimate,
            required_context_tokens=required_context_tokens,
            context_window=model.context_window,
            wall_seconds=round(time.perf_counter() - started, 3),
            warmup_seconds=warmup_metrics.get("warmup_seconds"),
            warmup_rss_peak_gb=warmup_metrics.get("warmup_rss_peak_gb"),
            warmup_rss_avg_gb=warmup_metrics.get("warmup_rss_avg_gb"),
            ollama_rss_peak_gb=memory_metrics.get("ollama_rss_peak_gb"),
            ollama_rss_avg_gb=memory_metrics.get("ollama_rss_avg_gb"),
            skipped_reason="model reported insufficient context window" if exc.context_related else "",
            error="" if exc.context_related else str(exc)[:500],
        )
    memory_metrics = monitor.stop()

    return ProbeResult(
        model=model.name,
        size_chars=size,
        status="ok",
        prompt_variant=prompt_variant,
        prompt_chars=len(prompt),
        estimated_prompt_tokens=prompt_tokens_estimate,
        required_context_tokens=required_context_tokens,
        context_window=model.context_window,
        warmup_seconds=warmup_metrics.get("warmup_seconds"),
        warmup_rss_peak_gb=warmup_metrics.get("warmup_rss_peak_gb"),
        warmup_rss_avg_gb=warmup_metrics.get("warmup_rss_avg_gb"),
        ollama_rss_peak_gb=memory_metrics.get("ollama_rss_peak_gb"),
        ollama_rss_avg_gb=memory_metrics.get("ollama_rss_avg_gb"),
        **metrics,
    )


def warmup_model(
    *,
    client: OllamaClient,
    model: ModelInfo,
    root: Path,
    num_predict: int,
    run_log: Path | None,
) -> dict[str, float | None]:
    prompt_variant = f"{model.name}:warmup:{time.time_ns()}"
    prompt = build_prompt(root, 500, variant=prompt_variant)
    prompt_tokens_estimate = estimate_tokens(prompt)
    required_context_tokens = prompt_tokens_estimate + max(4, min(num_predict, 16)) + 64
    write_run_event(
        run_log,
        {
            "event": "warmup_prompt",
            "model": model.name,
            "prompt_variant": prompt_variant,
            "prompt_chars": len(prompt),
            "estimated_prompt_tokens": prompt_tokens_estimate,
            "prompt": prompt,
        },
    )
    monitor = ProcessMemoryMonitor()
    monitor.start()
    started = time.perf_counter()
    try:
        client.chat_stream(
            model=model.name,
            prompt=prompt,
            num_predict=max(4, min(num_predict, 16)),
            required_context_tokens=required_context_tokens,
            context_window=model.context_window,
            stream_callback=lambda event: write_run_event(
                run_log,
                {
                    **event,
                    "model": model.name,
                    "size_chars": "warmup",
                    "prompt_variant": prompt_variant,
                },
            ),
        )
        error = ""
    except OllamaError as exc:
        error = str(exc)[:500]
    memory = monitor.stop()
    elapsed = round(time.perf_counter() - started, 3)
    write_run_event(
        run_log,
        {
            "event": "warmup_done",
            "model": model.name,
            "prompt_variant": prompt_variant,
            "warmup_seconds": elapsed,
            "error": error,
            **memory,
        },
    )
    return {
        "warmup_seconds": elapsed,
        "warmup_rss_peak_gb": memory.get("ollama_rss_peak_gb"),
        "warmup_rss_avg_gb": memory.get("ollama_rss_avg_gb"),
    }


def discover_models(client: OllamaClient) -> list[ModelInfo]:
    models: list[ModelInfo] = []
    for tag in client.list_models():
        name = str(tag.get("name") or tag.get("model") or "")
        show: dict[str, Any] = {}
        if name:
            try:
                show = client.show_model(name)
            except Exception:
                show = {}
        info = model_info_from_tags(tag, show)
        if info.name:
            models.append(info)
    return models


def parse_sizes(text: str) -> list[int]:
    sizes = [int(part.strip()) for part in text.split(",") if part.strip()]
    if not sizes or any(size <= 0 for size in sizes):
        raise argparse.ArgumentTypeError("sizes must be a comma-separated list of positive integers")
    return sizes


def iter_records(state: dict[str, Any]) -> Iterator[dict[str, Any]]:
    entries = state.get("entries") or {}
    for value in entries.values():
        if isinstance(value, dict) and value.get("status") in TERMINAL_STATUSES:
            yield value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=project_root_from_script())
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--sizes", type=parse_sizes, default=DEFAULT_SIZES)
    parser.add_argument("--models", default="", help="comma-separated fnmatch patterns; default: all Ollama models")
    parser.add_argument(
        "--max-parameter-size",
        default="",
        help="optional parameter cap, e.g. 10b for smoke tests; models with unknown parameter size are excluded",
    )
    parser.add_argument("--num-predict", type=int, default=64)
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--state", type=Path, default=project_root_from_script() / "ollama_speedtest" / "state.jsonl")
    parser.add_argument("--results", type=Path, default=project_root_from_script() / "ollama_speedtest" / "results.jsonl")
    parser.add_argument("--report", type=Path, default=project_root_from_script() / "ollama_speedtest" / "report.md")
    parser.add_argument("--run-log", type=Path, default=None, help="JSONL prompt and stream log; default: ollama_speedtest/run/<date>-<time>-<uid>.jsonl")
    parser.add_argument("--rerun", action="store_true", help="rerun terminal entries already present in state")
    parser.add_argument("--retry-errors", action="store_true", help="retry previous entries with status=error")
    args = parser.parse_args(argv)

    if args.num_predict <= 0:
        parser.error("--num-predict must be positive")

    root = args.root.resolve()
    if args.run_log is None:
        args.run_log = new_run_log_path(root)
    client = OllamaClient(args.endpoint, args.timeout)
    state = load_state(args.state)
    state.setdefault("created_at", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    save_state(args.state, state)

    try:
        discovered = discover_models(client)
    except Exception as exc:
        print(f"Ollama model discovery failed: {exc}", file=sys.stderr)
        return 2

    patterns = [part.strip() for part in args.models.split(",") if part.strip()]
    selected = select_models(
        discovered,
        patterns=patterns,
        max_parameter_size_b=parse_size_limit_b(args.max_parameter_size),
    )
    if not selected:
        print("No Ollama models matched the requested filters.")
        return 0

    print(f"Found {len(discovered)} Ollama model(s); running {len(selected)} after filters.")
    print(f"Prompt sizes: {', '.join(str(size) for size in args.sizes)} chars")
    print(f"State: {args.state}")
    print(f"Report: {args.report}")
    print(f"Run log: {args.run_log}")
    write_run_event(args.run_log, {"event": "run_started", "sizes": args.sizes, "models": [m.name for m in selected]})

    for model in selected:
        context = model.context_window if model.context_window is not None else "unknown"
        params = model.parameter_size or "unknown size"
        print(f"\nModel: {model.name} ({params}, context {context})")
        pending_sizes = [
            size for size in args.sizes
            if not should_skip_existing(
                state["entries"].get(entry_key(model.name, size)),
                rerun=args.rerun,
                retry_errors=args.retry_errors,
            )
        ]
        warmup_metrics: dict[str, float | None] = {}
        if pending_sizes:
            warmup_metrics = warmup_model(
                client=client,
                model=model,
                root=root,
                num_predict=args.num_predict,
                run_log=args.run_log,
            )
            print(
                f"  warmup: {fmt(warmup_metrics.get('warmup_seconds'))}s, "
                f"rss peak {fmt(warmup_metrics.get('warmup_rss_peak_gb'))} GB, "
                f"avg {fmt(warmup_metrics.get('warmup_rss_avg_gb'))} GB"
            )
        else:
            print("  warmup: skipped, all requested sizes are already terminal")
        for size in args.sizes:
            key = entry_key(model.name, size)
            existing = state["entries"].get(key)
            if should_skip_existing(existing, rerun=args.rerun, retry_errors=args.retry_errors):
                print(f"  {size:>6} chars: already {existing.get('status')}")
                continue

            prompt_variant = f"{model.name}:{size}:{time.time_ns()}"
            state["entries"][key] = {
                "model": model.name,
                "size_chars": size,
                "status": "running",
                "prompt_variant": prompt_variant,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }
            save_state(args.state, state, key)

            result = run_probe(
                client=client,
                model=model,
                root=root,
                size=size,
                num_predict=args.num_predict,
                prompt_variant=prompt_variant,
                warmup_metrics=warmup_metrics,
                run_log=args.run_log,
            )
            record = asdict(result)
            record["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            state["entries"][key] = record
            save_state(args.state, state, key)
            append_jsonl(args.results, record)
            write_report(args.report, iter_records(state))

            if result.status == "ok":
                prompt_tokens = result.prompt_tokens or result.estimated_prompt_tokens
                print(
                    f"  {size:>6} chars: ok, prompt {prompt_tokens} tok, "
                    f"prompt eval {fmt(result.prompt_eval_seconds)}s, "
                    f"first token {fmt(result.first_token_seconds)}s, "
                    f"gen {fmt(result.generation_tokens_per_second)} tok/s, "
                    f"{fmt(result.generation_chars_per_second)} chars/s, "
                    f"rss peak {fmt(result.ollama_rss_peak_gb)} GB, avg {fmt(result.ollama_rss_avg_gb)} GB"
                )
            elif result.status == "skipped":
                prompt_tokens = result.prompt_tokens or result.estimated_prompt_tokens
                print(f"  {size:>6} chars: skipped, prompt ~{prompt_tokens} tok, {result.skipped_reason}")
            else:
                prompt_tokens = result.prompt_tokens or result.estimated_prompt_tokens
                print(f"  {size:>6} chars: error, prompt ~{prompt_tokens} tok, {result.error[:160]}")

    write_report(args.report, iter_records(state))
    write_run_event(args.run_log, {"event": "run_done"})
    print("\nDone. Incremental state and report are up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
