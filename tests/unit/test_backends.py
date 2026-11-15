"""Unit tests for inference backends. No model and no vLLM install required."""

import json
import sys
import types
from pathlib import Path

import pytest
from pydantic import BaseModel

import siivila.backends as backends
from siivila.backends import (
    PRODUCTION_CONTEXT_LENGTH,
    BackendError,
    FakeBackend,
    MlxBackend,
    VllmBackend,
    create_backend,
)


class HealthCheck(BaseModel):
    operational: bool
    message: str


class TestFakeBackend:
    def test_returns_one_output_per_prompt(self):
        backend = FakeBackend()
        results = backend.generate(["a", "b", "c"], HealthCheck)
        assert len(results) == 3
        assert all(isinstance(r, HealthCheck) for r in results)

    def test_records_calls(self):
        backend = FakeBackend()
        backend.generate(["hello"], HealthCheck)
        assert backend.calls == [("hello", HealthCheck)]

    def test_custom_responder(self):
        backend = FakeBackend(
            responder=lambda _p, schema: schema(operational=True, message="ok")
        )
        [result] = backend.generate(["ping"], HealthCheck)
        assert result.operational is True


class _FakeCompletion:
    def __init__(self, text: str):
        self.text = text


class _FakeRequestOutput:
    def __init__(self, text: str):
        self.outputs = [_FakeCompletion(text)]


def _install_fake_vllm(monkeypatch, llm_instance):
    module = types.ModuleType("vllm")
    module.LLM = lambda **kwargs: llm_instance

    class SamplingParams:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    module.SamplingParams = SamplingParams
    sampling_params = types.ModuleType("vllm.sampling_params")

    class StructuredOutputsParams:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    sampling_params.StructuredOutputsParams = StructuredOutputsParams
    monkeypatch.setitem(sys.modules, "vllm", module)
    monkeypatch.setitem(sys.modules, "vllm.sampling_params", sampling_params)
    return llm_instance


class _FakeLLM:
    """Stands in for vllm.LLM; serves queued responses, then repeats the last."""

    def __init__(self):
        self.init_kwargs: dict | None = None
        self.responses: list[str] = []
        self.prompts_seen: list[str] = []

    def generate(self, prompts, _params):
        self.prompts_seen.extend(prompts)
        return [_FakeRequestOutput(self.responses.pop(0)) for _ in prompts]


@pytest.fixture
def model_dir(tmp_path: Path) -> Path:
    path = tmp_path / "model"
    path.mkdir()
    return path


class TestVllmBackend:
    def test_missing_model_path_fails_without_importing_vllm(self, tmp_path, monkeypatch):
        monkeypatch.delitem(sys.modules, "vllm", raising=False)
        with pytest.raises(BackendError, match="model path does not exist"):
            VllmBackend(tmp_path / "no-such-model")
        assert "vllm" not in sys.modules

    def test_missing_vllm_package_fails_clearly(self, model_dir, monkeypatch):
        monkeypatch.setitem(sys.modules, "vllm", None)
        with pytest.raises(BackendError, match="vllm is not installed"):
            VllmBackend(model_dir)

    def test_loads_model_with_production_context(self, model_dir, monkeypatch):
        llm = _FakeLLM()
        fake_vllm_holder = {}

        def capture_llm(**kwargs):
            fake_vllm_holder["kwargs"] = kwargs
            return llm

        module = types.ModuleType("vllm")
        module.LLM = capture_llm
        module.SamplingParams = type("SamplingParams", (), {"__init__": lambda s, **k: None})
        sp = types.ModuleType("vllm.sampling_params")
        sp.StructuredOutputsParams = type("StructuredOutputsParams", (), {"__init__": lambda s, **k: None})
        monkeypatch.setitem(sys.modules, "vllm", module)
        monkeypatch.setitem(sys.modules, "vllm.sampling_params", sp)

        VllmBackend(model_dir)
        assert fake_vllm_holder["kwargs"]["model"] == str(model_dir)
        assert fake_vllm_holder["kwargs"]["max_model_len"] == PRODUCTION_CONTEXT_LENGTH

    def test_generate_returns_validated_models(self, model_dir, monkeypatch):
        llm = _install_fake_vllm(monkeypatch, _FakeLLM())
        llm.responses = [json.dumps({"operational": True, "message": "ok"})]
        backend = VllmBackend(model_dir)
        [result] = backend.generate(["health?"], HealthCheck)
        assert result.operational is True

    def test_invalid_output_retries_then_raises(self, model_dir, monkeypatch):
        llm = _install_fake_vllm(monkeypatch, _FakeLLM())
        llm.responses = ["not json", "still not json", '{"wrong": "shape"}']
        backend = VllmBackend(model_dir)
        with pytest.raises(BackendError, match="schema-invalid output"):
            backend.generate(["health?"], HealthCheck)
        assert len(llm.prompts_seen) == 3  # initial + 2 retries

    def test_retry_succeeds_on_second_attempt(self, model_dir, monkeypatch):
        llm = _install_fake_vllm(monkeypatch, _FakeLLM())
        llm.responses = ["garbage", json.dumps({"operational": False, "message": "meh"})]
        backend = VllmBackend(model_dir)
        [result] = backend.generate(["health?"], HealthCheck)
        assert result.operational is False
        assert "did not match the required JSON schema" in llm.prompts_seen[1]


class _FakeTokenizer:
    def __init__(self, with_chat_template: bool):
        self.chat_template = "<user>{{x}}" if with_chat_template else None

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=True):
        return "CHAT::" + messages[0]["content"]


def _install_fake_mlx(monkeypatch, generate_fn, with_chat_template=False):
    module = types.ModuleType("mlx_lm")
    module.load = lambda _path: ("MODEL", _FakeTokenizer(with_chat_template))
    module.generate = generate_fn
    monkeypatch.setitem(sys.modules, "mlx_lm", module)


class TestMlxBackend:
    def test_missing_package_fails_clearly(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "mlx_lm", None)
        with pytest.raises(BackendError, match="mlx-lm is not installed"):
            MlxBackend("any-model")

    def test_unloadable_model_fails_clearly(self, monkeypatch):
        module = types.ModuleType("mlx_lm")

        def _load(_path):
            raise RuntimeError("not a model")

        module.load = _load
        monkeypatch.setitem(sys.modules, "mlx_lm", module)
        with pytest.raises(BackendError, match="cannot load model"):
            MlxBackend("bad-model")

    def test_generate_validates_against_schema(self, monkeypatch):
        seen = []

        def generate(_m, _t, prompt, max_tokens, verbose):
            seen.append(prompt)
            return json.dumps({"operational": True, "message": "ok"})

        _install_fake_mlx(monkeypatch, generate)
        backend = MlxBackend("some-model")
        [result] = backend.generate(["health?"], HealthCheck)
        assert result.operational is True
        assert "json" in seen[0].lower()  # schema instruction appended

    def test_prose_wrapped_json_is_extracted(self, monkeypatch):
        generate = lambda *_a, **_k: (
            '<think>schema has {"findings": []}</think>\n'
            'Sure! {"operational": false, "message": "x"} done'
        )
        _install_fake_mlx(monkeypatch, generate)
        [result] = MlxBackend("m").generate(["p"], HealthCheck)
        assert result.operational is False

    def test_chat_template_applied_when_available(self, monkeypatch):
        seen = []
        generate = lambda _m, _t, prompt, **k: seen.append(prompt) or '{"operational": true, "message": "ok"}'
        _install_fake_mlx(monkeypatch, generate, with_chat_template=True)
        MlxBackend("m").generate(["health?"], HealthCheck)
        assert seen[0].startswith("CHAT::")

    def test_invalid_output_retries_then_raises(self, monkeypatch):
        prompts = []

        def generate(_m, _t, prompt, **k):
            prompts.append(prompt)
            return "not json at all"

        _install_fake_mlx(monkeypatch, generate)
        backend = MlxBackend("m")
        with pytest.raises(BackendError, match="schema-invalid output"):
            backend.generate(["health?"], HealthCheck)
        assert len(prompts) == 3  # initial + 2 retries
        assert "did not match the required JSON schema" in prompts[1]


class TestCreateBackend:
    def test_auto_prefers_vllm(self, monkeypatch, tmp_path):
        sentinel = object()
        monkeypatch.setattr(backends, "VllmBackend", lambda *_a, **_k: sentinel)
        monkeypatch.setattr(
            backends.importlib.util, "find_spec",
            lambda name: object() if name == "vllm" else None,
        )
        assert create_backend("auto", tmp_path) is sentinel

    def test_auto_falls_back_to_mlx(self, monkeypatch, tmp_path):
        sentinel = object()
        monkeypatch.setattr(backends, "MlxBackend", lambda *_a, **_k: sentinel)
        monkeypatch.setattr(
            backends.importlib.util, "find_spec",
            lambda name: object() if name == "mlx_lm" else None,
        )
        assert create_backend("auto", tmp_path) is sentinel

    def test_auto_with_neither_installed_fails(self, monkeypatch, tmp_path):
        monkeypatch.setattr(backends.importlib.util, "find_spec", lambda _n: None)
        with pytest.raises(BackendError, match="no inference backend available"):
            create_backend("auto", tmp_path)

    def test_explicit_mlx_is_used(self, monkeypatch, tmp_path):
        sentinel = object()
        monkeypatch.setattr(backends, "MlxBackend", lambda *_a, **_k: sentinel)
        assert create_backend("mlx", tmp_path) is sentinel

    def test_explicit_vllm_with_missing_framework_fails(self, tmp_path):
        # vllm is not installed in the test environment
        with pytest.raises(BackendError, match="vllm is not installed"):
            create_backend("vllm", tmp_path)
