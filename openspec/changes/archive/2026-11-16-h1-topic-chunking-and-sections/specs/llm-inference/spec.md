# Spec Delta

## MODIFIED Requirements

### Requirement: Structured output support
Every backend SHALL deliver output that validates against a requested Pydantic schema, applying the model tokenizer's chat template when available (with thinking disabled when supported) and setting an explicit maximum output token bound so responses do not truncate mid-schema; where the engine supports guided decoding (vLLM) it SHALL be used, and otherwise the backend SHALL enforce the schema through validation with bounded retries.

#### Scenario: Schema-constrained generation
- **WHEN** a pipeline step requests output conforming to a given schema
- **THEN** the returned object parses as JSON and validates against that schema

#### Scenario: Chat template and token bound parity across backends
- **WHEN** either the MLX or vLLM backend generates a response for a model whose tokenizer defines a chat template
- **THEN** the prompt is formatted with that chat template and generation is bounded by `DEFAULT_MAX_TOKENS`

#### Scenario: Retry on invalid output
- **WHEN** a model response fails schema validation
- **THEN** the backend retries the request a bounded number of times before marking the step as failed
