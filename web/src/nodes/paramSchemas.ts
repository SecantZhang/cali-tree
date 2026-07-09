// Static mirror of the backend's param_schema dicts (node_db/node_preprocessing/
// node_vejudge/node_eval executors). Drives the Inspector's schema-driven form. Keep in
// sync with the backend; task-11-era work may switch this to be fetched live from
// GET /api/nodes.

export type ParamFieldType = 'string' | 'number' | 'bool' | 'enum' | 'list[string]' | 'list[enum]'

export interface ParamField {
  type: ParamFieldType
  default: unknown
  options?: string[]
  min?: number
  max?: number
  step?: number
}

// M1/M3 = text modality, M2/M4/M5/M6 = video modality (vejudge/core/rubric/definitions.py).
const TEXT_JUDGES = ['M1', 'M3']
const VIDEO_JUDGES = ['M2', 'M4', 'M5', 'M6']

const PREPROCESSING_ARTIFACT_TYPES = [
  'sampled_frames', 'keyframes', 'short_clips', 'asr_transcript', 'ocr_text',
  'captions', 'shot_boundaries', 'audio_event_labels', 'blur_flicker_metrics',
]

// No "full" mode — sampling_ratio: 1.0 (the default) already selects every item under
// either mode below, so a dedicated mode that ignored ratio entirely was redundant and a
// footgun (it silently no-oped ratio for anyone who changed the ratio but not the mode).
const SAMPLING_FIELDS: Record<string, ParamField> = {
  sampling_ratio: { type: 'number', default: 1.0, min: 0, max: 1, step: 0.05 },
  sampling_mode: {
    type: 'enum', options: ['unified', 'stratified'], default: 'unified',
  },
  use_case_filter: { type: 'list[string]', default: null },
  item_id_pattern: { type: 'string', default: null },
  // Restricts the sampling pool to items with a human label before ratio/mode is applied
  // — guarantees a downstream Eval node never lands on 0 overlap by bad luck.
  require_labels: { type: 'bool', default: false },
}

export const NODE_PARAM_SCHEMAS: Record<string, Record<string, ParamField>> = {
  peanut_source: {
    model: { type: 'string', default: 'peanut' },
    projects: { type: 'list[string]', default: null },
  },
  dataset: { ...SAMPLING_FIELDS },
  preprocessing: {
    artifact_types: { type: 'list[enum]', options: PREPROCESSING_ARTIFACT_TYPES, default: null },
    input_strategy: { type: 'enum', options: ['A', 'B', 'C', 'D', 'E'], default: 'A' },
    cache_policy: {
      type: 'enum', options: ['reuse_if_present', 'force_recompute'], default: 'reuse_if_present',
    },
  },
  // model/temperature default to the actual value LMEngine falls back to when unset
  // (config.DEFAULT_TEXT_MODEL, LMEngine.__init__'s own temperature=0.3/max_tokens=4096) —
  // shown explicitly rather than as a blank field so editing the node shows what will
  // really run, not an ambiguous empty box.
  lm_engine: {
    engine_kind: {
      type: 'enum',
      options: ['gemini', 'gpt', 'qwen', 'claude', 'deepseek', 'llama', 'kimi'],
      default: 'gpt',
    },
    // Rendered as a dropdown scoped to the selected engine_kind (see modelCatalog.ts and
    // LMEngineNode.tsx's fieldOverrides), not a free-text input — `default` here only
    // seeds `defaultParamsFor`'s initial value.
    model: { type: 'string', default: 'gpt-4.1' },
    temperature: { type: 'number', default: 0.3 },
    max_tokens: { type: 'number', default: 4096, min: 1 },
    concurrency: { type: 'number', default: 1, min: 1 },
    health_check: { type: 'bool', default: false },
  },
  // engine_kind/model/temperature/concurrency come from a required upstream LM Engine
  // Node's `engine_config` input, not this node's own params (see lm_engine_node.py).
  judge_text: {
    metrics: { type: 'list[enum]', options: TEXT_JUDGES, default: null },
    batch_size: { type: 'number', default: 1, min: 1 },
  },
  judge_video: {
    metrics: { type: 'list[enum]', options: VIDEO_JUDGES, default: null },
    batch_size: { type: 'number', default: 1, min: 1 },
  },
  eval_text: {},
  eval_video: {},
}

export function defaultParamsFor(nodeType: string): Record<string, unknown> {
  const schema = NODE_PARAM_SCHEMAS[nodeType] ?? {}
  const params: Record<string, unknown> = {}
  for (const [key, field] of Object.entries(schema)) {
    params[key] = field.default
  }
  return params
}
