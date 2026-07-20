// Static mirror of the backend's param_schema dicts (node_db/node_preprocessing/
// node_vejudge/node_eval executors). Drives the Inspector's schema-driven form. Keep in
// sync with the backend; task-11-era work may switch this to be fetched live from
// GET /api/nodes.

export type ParamFieldType =
  | 'string' | 'text' | 'number' | 'bool' | 'enum' | 'list[string]' | 'list[enum]'

export interface ParamField {
  type: ParamFieldType
  default: unknown
  options?: string[]
  min?: number
  max?: number
  step?: number
}

// M1-M6 built-in metric presets on the Judge Prompt node (vejudge/core/rubric/
// definitions.py), plus a "custom" free-text mode.
const METRIC_PRESETS = ['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'custom']
// The human dimensions a custom judge may target (dl_human_annotations HUMAN_DIMENSIONS).
const HUMAN_DIMENSIONS = [
  'voiceover_matches_visuals', 'abrupt_cutoffs_voiceover', 'abrupt_cutoffs_video',
  'story_flow_voiceover', 'story_flow_visuals', 'section_placement_opening',
  'section_placement_middle', 'section_placement_closing', 'video_addresses_prompt',
]

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
  // One source node per model (Peanut/Coconut/Grapenut); wire several into one Dataset
  // node (its raw_dataset is a fan-in socket) to calibrate across models. Each loads its
  // own model; `projects` optionally restricts to a subset.
  peanut_source: { projects: { type: 'list[string]', default: null } },
  coconut_source: { projects: { type: 'list[string]', default: null } },
  grapenut_source: { projects: { type: 'list[string]', default: null } },
  // No params — loads the whole VE-Bench DB; sample/subset downstream in the Dataset node.
  vebench_source: {},
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
  // A metric's identity (prompt/schema/alignment) is now a wired `judge_spec` from a Judge
  // Prompt node, not params here. Presets M1-M6 reuse the built-in code; "custom" enables a
  // free-text judge (the custom-only fields are ignored unless preset === 'custom').
  judge_prompt: {
    preset: { type: 'enum', options: METRIC_PRESETS, default: 'M1' },
    spec_id: { type: 'string', default: 'custom' },
    label: { type: 'string', default: null },
    modality: { type: 'enum', options: ['text', 'video'], default: 'text' },
    system: { type: 'text', default: null },
    user_template: { type: 'text', default: null },
    expected_fields: { type: 'list[string]', default: null },
    score_path: { type: 'string', default: 'score_1_to_5' },
    target_dimension: { type: 'enum', options: HUMAN_DIMENSIONS, default: HUMAN_DIMENSIONS[0] },
  },
  // engine_kind/model/temperature/concurrency come from a required upstream LM Engine Node's
  // `engine_config` input; the metric comes from a required `judge_spec` input.
  judge: {
    batch_size: { type: 'number', default: 1, min: 1 },
  },
  eval: {},
  // judge_engine/human_engine come from two required upstream LM Engine Node
  // `engine_config` inputs; `judge_result` (a Judge Node's output) supplies the anchor
  // score and metric identity — there's no metric_id param, the metric is a wired
  // artifact same as everywhere else in this node system. `labels` is optional (used
  // only for the secondary tab's judge-vs-human score comparison, not the debate itself).
  cl_adversarial: {
    epsilon: { type: 'number', default: 0.25, min: 0, step: 0.05 },
    max_rounds: { type: 'number', default: 4, min: 1 },
    retrieval_enabled: { type: 'bool', default: true },
    batch_size: { type: 'number', default: 1, min: 1 },
    // "" (default) = auto-detect via the ALIGNMENT crosswalk; set only for metrics
    // (M1/M2/M4) with no direct human-dimension mapping.
    human_dimension_override: { type: 'enum', options: ['', ...HUMAN_DIMENSIONS], default: '' },
    // Opt-in: when a real human label exists for an item, convergence requires
    // closing the gap to it, not just round-to-round self-stability. Off by default —
    // changes what the debate optimizes for, so it's a deliberate choice.
    ground_in_human_labels: { type: 'bool', default: false },
  },
  cl_rule_tree: {
    max_questions: { type: 'number', default: 5, min: 1 },
    batch_size: { type: 'number', default: 1, min: 1 },
    // "" (default) = auto-detect the human dimension(s) via the ALIGNMENT crosswalk.
    human_dimension_override: { type: 'enum', options: ['', ...HUMAN_DIMENSIONS], default: '' },
  },
  // No params — it just renders the upstream judge_rule report.
  cl_rule_eval: {},
  // No params — frames the upstream metrics_report.
  alignment_report: {},
  cl_semantic_tree: {
    max_questions: { type: 'number', default: 5, min: 1 },
    batch_size: { type: 'number', default: 1, min: 1 },
    // "" (default) = auto-detect the human dimension(s) via the ALIGNMENT crosswalk.
    human_dimension_override: { type: 'enum', options: ['', ...HUMAN_DIMENSIONS], default: '' },
  },
}

export function defaultParamsFor(nodeType: string): Record<string, unknown> {
  const schema = NODE_PARAM_SCHEMAS[nodeType] ?? {}
  const params: Record<string, unknown> = {}
  for (const [key, field] of Object.entries(schema)) {
    params[key] = field.default
  }
  return params
}
