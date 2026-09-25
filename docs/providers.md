# Official OpenAI and Gemini APIs

The default configuration no longer requires the company proxy. Direct support is
implemented for OpenAI (`gpt`) and Google Gemini (`gemini`) only. Other existing
engine classes remain for historical workflows and need explicit legacy configuration.

| Engine | Key | Default API base |
| --- | --- | --- |
| `gpt` | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| `gemini` | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | `https://generativelanguage.googleapis.com/v1beta` |

Set keys in your shell, project-root `.env` (see `.env.example`), or Settings → API
Credentials. Select the provider before saving a key in the UI. A blank Base URL uses
that provider's official endpoint. Saving or clearing one provider leaves the other intact.
Credentials are written to a gitignored local JSON file with owner-only permissions;
the API returns status and endpoint only, never saved keys.

Resolution within a provider: saved settings > shell variables > project `.env`.
`GEMINI_API_KEY` takes precedence over the `GOOGLE_API_KEY` alias. Base URLs can be
changed with `OPENAI_BASE_URL`/`GEMINI_BASE_URL`; these must point to the corresponding
API protocol (Chat Completions / GenerateContent). The Gemini URL ends at `/v1beta`,
not `/v1beta/openai`. No implicit mirror or cross-provider key fallback is used.

## Models and experiment behavior

Graph engines route by engine kind. AURORA standalone judge/optimizer clients route
by model prefix (`gpt-*`, `o1/o3/o4`, `text-embedding-*`, `gemini-*`). Set the model
in the workflow/CLI as before; no historical workflow or prompt is rewritten.
Unknown standalone model IDs need an explicit `VEJUDGE_PROVIDER=openai|gemini` override.
That override applies process-wide, so leave it unset for mixed-provider workflows.

OpenAI uses Chat Completions with `max_completion_tokens`. GPT-5.1/5.2/5.4 sampling
uses `reasoning_effort=none`, including the AURORA `gpt-5.4-mini` configuration.
Earlier GPT-5 and o-series reasoning models require temperature 1 in this adapter;
unsupported sampling settings fail explicitly rather than changing an experiment's
temperature silently. Model availability still depends on the provider/account. Use
chat/vision models in judge nodes, not image-generation, video-generation, or embedding
model IDs from historical proxy catalogs.

Gemini uses native GenerateContent with system instructions and inline media. Returned
text, usage (including thought tokens), model version, and endpoint are normalized into
the existing engine contract. Gemini blocking/no-text responses surface as errors.
Images and short videos are supported; inline media above 19 MB encoded is rejected
with guidance to use shorter clips or sampled frames. Large-file uploads through the
Gemini Files API are not implemented in this change. OpenAI continues to accept image
frames; its existing engine rejects raw video input.

Tree embedding calls resolve credentials independently of the judge: the existing
`text-embedding-*` models require an OpenAI key even with a Gemini judge. Flat
Rubric-Lite/AURORA runs do not need those embeddings. TextGrad and the isolated AURORA
GEPA worker use the selected optimizer's provider; the older GEPA baseline stays OpenAI.

Start a new experiment directory when switching providers: existing checkpoints remain
authoritative for old runs and are not invalidated by a credential change.

All existing `--live`/`allow_live` gates still apply. This migration's tests use mocked
responses/local mock servers and do not contact paid model APIs.

## Optional smoke checks

After adding your keys, explicitly authorize one small call:

```bash
.venv/bin/python -m vejudge.lm_engine --engine gpt --model gpt-4.1-mini --live
.venv/bin/python -m vejudge.lm_engine --engine gemini --model gemini-2.5-flash --live
```

## Historical proxy configuration

Old `CHAT_GPT_API_KEY`, `AZURE_OPENAI_API_KEY`, `OPENAI_COMPAT_BASE_URL`,
`LLM_PROXY_BASE_URL`, `LLM_PROXY_MIRROR_URL`, unscoped saved credentials, and `.env-raw`
are ignored by default. To intentionally reproduce an old proxy environment, explicitly
set `VEJUDGE_PROVIDER=legacy`. Supplying an `env_raw_path` argument in Python also opts
into legacy mode. Direct keys are never combined with those legacy endpoints.

## API references

- [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini)
- [Gemini GenerateContent](https://ai.google.dev/api/generate-content)
- [Gemini video inputs](https://ai.google.dev/gemini-api/docs/video-understanding)
