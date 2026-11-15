"""Inference backends.

Everything model-facing goes through the ModelBackend protocol so unit tests
run against FakeBackend without loading a model, and the (later) LangGraph
workflow never depends on framework specifics:

- FakeBackend  → unit tests (no model, no framework imports)
- MLXBackend   → local macOS runs (mlx-lm, dev-only dependency)
- VllmBackend  → Roihu production (direct vLLM offline API, no API server)

vLLM and mlx-lm are imported lazily inside backend methods: neither is
installed in every environment.
"""

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

#: Context length for the production model (see README processing strategy).
PRODUCTION_CONTEXT_LENGTH = 65536

#: How many extra attempts follow a schema-invalid response before failing.
DEFAULT_MAX_RETRIES = 2

#: How many tokens a single response may use, for backends that need a bound.
DEFAULT_MAX_TOKENS = 4096


class BackendError(Exception):
    """Raised when the backend cannot serve a request."""


class ModelBackend(Protocol):
    """Minimal model interface: schema-constrained generation."""

    def generate(self, prompts: list[str], schema: type[T]) -> list[T]:
        """Generate one schema-valid output per prompt.

        Raises BackendError if a prompt has produced only invalid output
        after the backend's bounded retries.
        """
        ...


class FakeBackend:
    """In-memory backend for tests. Records calls, never loads a model."""

    def __init__(self, responder: Callable[[str, type[T]], T] | None = None) -> None:
        self.calls: list[tuple[str, type[BaseModel]]] = []
        self._responder = responder or (lambda _prompt, schema: schema.model_construct())

    def generate(self, prompts: list[str], schema: type[T]) -> list[T]:
        self.calls.extend((prompt, schema) for prompt in prompts)
        return [self._responder(prompt, schema) for prompt in prompts]


def _schema_instruction(schema: type[BaseModel]) -> str:
    return (
        "Respond with only a JSON object matching this JSON schema, "
        "with no prose around it:\n"
        + json.dumps(schema.model_json_schema())
    )


def _retry_prompt(prompt: str) -> str:
    return (
        "Your previous answer did not match the required JSON schema. "
        "Answer again with only the JSON object.\n\n" + prompt
    )


class MlxBackend:
    """Local Apple Silicon inference via mlx-lm.

    mlx-lm has no guided decoding, so schema enforcement is prompt +
    Pydantic validation + bounded retry.
    """

    def __init__(self, model_path: str) -> None:
        try:
            from mlx_lm import load
        except ImportError as exc:
            raise BackendError(
                "mlx-lm is not installed; it is a dev dependency — run: uv sync"
            ) from exc
        try:
            self._model, self._tokenizer = load(str(model_path))
        except Exception as exc:
            raise BackendError(f"cannot load model {model_path}: {exc}") from exc

    def generate(self, prompts: list[str], schema: type[T]) -> list[T]:
        from mlx_lm import generate as mlx_generate

        results: list[T] = []
        for prompt in prompts:
            full_prompt = prompt + "\n\n" + _schema_instruction(schema)
            text = self._complete(mlx_generate, full_prompt)
            results.append(self._validated(mlx_generate, full_prompt, text, schema))
        return results

    def _complete(self, mlx_generate: Callable[..., str], prompt: str) -> str:
        return mlx_generate(
            self._model,
            self._tokenizer,
            prompt=self._chat(prompt),
            max_tokens=DEFAULT_MAX_TOKENS,
            verbose=False,
        )

    def _chat(self, prompt: str) -> str:
        template = getattr(self._tokenizer, "chat_template", None)
        if template:
            messages = [{"role": "user", "content": prompt}]
            try:
                return self._tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                return self._tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                )
        return prompt

    def _validated(
        self, mlx_generate: Callable[..., str], prompt: str, text: str, schema: type[T]
    ) -> T:
        for attempt in range(DEFAULT_MAX_RETRIES + 1):
            try:
                return schema.model_validate_json(_extract_json(text))
            except ValidationError:
                if attempt >= DEFAULT_MAX_RETRIES:
                    raise BackendError(
                        f"model produced schema-invalid output {attempt + 1} times "
                        f"for schema {schema.__name__}"
                    ) from None
                text = self._complete(mlx_generate, _retry_prompt(prompt))
        raise BackendError("unreachable")


class VllmBackend:
    """Direct vLLM offline inference. No API server, no network listener."""

    def __init__(self, model_path: Path) -> None:
        if not model_path.is_dir():
            raise BackendError(f"model path does not exist or is not a directory: {model_path}")
        try:
            from vllm import LLM
        except ImportError as exc:
            raise BackendError(
                "vllm is not installed; install it in the active environment "
                "(on Roihu: the scratch venv, see slurm/grade.slurm header)"
            ) from exc
        self._llm = LLM(model=str(model_path), max_model_len=PRODUCTION_CONTEXT_LENGTH)

    def generate(self, prompts: list[str], schema: type[T]) -> list[T]:
        from vllm import SamplingParams
        from vllm.sampling_params import StructuredOutputsParams

        params = SamplingParams(
            temperature=0.0,
            structured_outputs=StructuredOutputsParams(json=schema.model_json_schema()),
        )
        outputs = self._llm.generate(prompts, params)
        results: list[T] = []
        for prompt, output in zip(prompts, outputs, strict=True):
            results.append(self._validated(prompt, output.outputs[0].text, schema, params))
        return results

    def _validated(self, prompt: str, text: str, schema: type[T], params: object) -> T:
        for attempt in range(DEFAULT_MAX_RETRIES + 1):
            try:
                return schema.model_validate_json(text)
            except ValidationError:
                if attempt >= DEFAULT_MAX_RETRIES:
                    raise BackendError(
                        f"model produced schema-invalid output {attempt + 1} times "
                        f"for schema {schema.__name__}"
                    ) from None
                retry = self._llm.generate([_retry_prompt(prompt)], params)
                text = retry[0].outputs[0].text
        raise BackendError("unreachable")


def _extract_json(text: str) -> str:
    """Best-effort extraction of a JSON object from model prose."""
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[-1]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


def create_backend(kind: str, model_path: Path) -> ModelBackend:
    """Select a backend. `auto` prefers vLLM and falls back to MLX."""
    if kind == "vllm":
        return VllmBackend(model_path)
    if kind == "mlx":
        return MlxBackend(str(model_path))
    if kind == "auto":
        if importlib.util.find_spec("vllm") is not None:
            return VllmBackend(model_path)
        if importlib.util.find_spec("mlx_lm") is not None:
            return MlxBackend(str(model_path))
        raise BackendError(
            "no inference backend available: neither vllm nor mlx-lm is installed"
        )
    raise BackendError(f"unknown backend: {kind}")
