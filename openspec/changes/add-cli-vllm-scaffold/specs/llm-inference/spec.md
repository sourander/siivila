# Spec Delta

## Purpose

Provides direct local vLLM inference from Python — no API server — so that criterion evaluation runs the same backend code on a developer laptop and on CSC Roihu's GH200 GPUs.

## ADDED Requirements

### Requirement: Direct vLLM inference
The system SHALL call vLLM directly from Python using its offline inference API and SHALL NOT depend on an OpenAI-compatible API server, SSH tunnel, or any network service to reach the model.

#### Scenario: Inference without a server
- **WHEN** the pipeline requests a completion
- **THEN** the request is served by an in-process vLLM engine with no network listener involved

### Requirement: Configurable model path
The system SHALL load model weights from the path given by `--model-path`, supporting both a small local model on Apple Silicon and the production model on Roihu, and SHALL configure the production model for approximately 64K context.

#### Scenario: Loading the production model on Roihu
- **WHEN** the CLI runs with `--model-path /scratch/project_1234/vllm-models/production-model` on a GH200 node
- **THEN** the model loads with approximately 64K context and is ready for inference

#### Scenario: Model path does not exist
- **WHEN** `--model-path` points to a directory that does not exist or contains no loadable model
- **THEN** the system exits with a non-zero code and a clear error before starting the pipeline

### Requirement: Structured output support
The backend SHALL support constraining model output to a JSON schema so that downstream Pydantic validation receives parseable, schema-shaped responses.

#### Scenario: Schema-constrained generation
- **WHEN** a pipeline step requests output conforming to a given JSON schema
- **THEN** the model's response parses as JSON and validates against that schema

#### Scenario: Retry on invalid output
- **WHEN** a model response fails schema validation
- **THEN** the system retries the request a bounded number of times before marking the step as failed

### Requirement: Local observability
In local development the system SHALL support tracing LLM calls (inputs, outputs, latency, token counts) to an observability backend such as Langfuse, and SHALL run with tracing disabled when no observability configuration is present.

#### Scenario: Traced local call
- **WHEN** a developer runs the CLI locally with observability environment variables set
- **THEN** each LLM call produces a trace visible in the configured observability backend

#### Scenario: Untraced run by default
- **WHEN** no observability configuration is present
- **THEN** the pipeline runs identically with tracing disabled and no observability connection attempted
