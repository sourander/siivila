# Spec Delta

## Purpose

Provides in-process LLM inference behind a single backend protocol — FakeBackend for unit tests, MLXBackend for local macOS runs, VLLMBackend for Roihu production — with no API server anywhere.

## ADDED Requirements

### Requirement: Direct in-process inference
The system SHALL run inference in-process on both environments: the vLLM offline Python API in production and MLX on local macOS. It SHALL NOT depend on an OpenAI-compatible API server, SSH tunnel, or any network service to reach a model.

#### Scenario: Inference without a server
- **WHEN** the pipeline requests a completion on either environment
- **THEN** the request is served by an in-process engine with no network listener involved

### Requirement: Pluggable inference backends
The system SHALL provide three backends behind one protocol — a fake in-memory backend for unit tests, an MLX backend for local macOS runs, and a vLLM backend for production — and the CLI SHALL select among them, defaulting to automatic selection that prefers vLLM and falls back to MLX.

#### Scenario: Unit tests need no model
- **WHEN** unit tests inject the fake backend
- **THEN** the full pipeline runs without loading any model or importing any inference framework

#### Scenario: Automatic selection on a Mac
- **WHEN** the CLI runs on macOS without vLLM installed and no explicit backend choice
- **THEN** the MLX backend is selected

#### Scenario: Explicit backend choice
- **WHEN** the CLI is invoked with `--backend vllm` but vLLM is not installed
- **THEN** the system exits with a non-zero code and a clear error instead of silently falling back

### Requirement: Configurable model path
The system SHALL load model weights from the path given by `--model-path` — a local or Hugging Face model for MLX, a weights directory for vLLM — and SHALL configure the production model for approximately 64K context.

#### Scenario: Loading the production model on Roihu
- **WHEN** the CLI runs with the vLLM backend and `--model-path /scratch/project_1234/vllm-models/production-model` on a GH200 node
- **THEN** the model loads with approximately 64K context and is ready for inference

#### Scenario: Model path does not exist
- **WHEN** `--model-path` points to something the selected backend cannot load
- **THEN** the system exits with a non-zero code and a clear error before starting the pipeline

### Requirement: Structured output support
Every backend SHALL deliver output that validates against a requested Pydantic schema; where the engine supports guided decoding (vLLM) it SHALL be used, and otherwise the backend SHALL enforce the schema through validation with bounded retries.

#### Scenario: Schema-constrained generation
- **WHEN** a pipeline step requests output conforming to a given schema
- **THEN** the returned object parses as JSON and validates against that schema

#### Scenario: Retry on invalid output
- **WHEN** a model response fails schema validation
- **THEN** the backend retries the request a bounded number of times before marking the step as failed

### Requirement: Local observability
In local development the system SHALL support tracing LLM calls (inputs, outputs, latency, token counts) to an observability backend such as Langfuse, and SHALL run with tracing disabled when no observability configuration is present.

#### Scenario: Traced local call
- **WHEN** a developer runs the CLI locally with observability environment variables set
- **THEN** each LLM call produces a trace visible in the configured observability backend

#### Scenario: Untraced run by default
- **WHEN** no observability configuration is present
- **THEN** the pipeline runs identically with tracing disabled and no observability connection attempted
