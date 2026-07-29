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
const IMAGENHUB_EDITORS = [
  'CycleDiffusion', 'DiffEdit', 'Imagic', 'InstructPix2Pix', 'MagicBrush',
  'Pix2PixZero', 'Prompt2prompt', 'SDEdit', 'Text2Live',
]
const PUBLIC_IMAGENMUSEUM_EDITORS = IMAGENHUB_EDITORS.filter((editor) => editor !== 'Imagic')

const PREPROCESSING_ARTIFACT_TYPES = [
  'sampled_frames', 'keyframes', 'short_clips', 'asr_transcript', 'ocr_text',
  'captions', 'shot_boundaries', 'audio_event_labels', 'blur_flicker_metrics',
]

// No "full" mode — sampling_ratio: 1.0 (the default) already selects every item under
// either mode below, so a dedicated mode that ignored ratio entirely was redundant and a
// footgun (it silently no-oped ratio for anyone who changed the ratio but not the mode).
const SAMPLING_FIELDS: Record<string, ParamField> = {
  // Dual-purpose: a value ≤ 1 is a fraction (0.5 = 50%); a value > 1 is an absolute item
  // count (5 = five items). No `max` so counts above 1 are allowed. Ignored when
  // `full_dataset` is on.
  sampling_ratio: { type: 'number', default: 1.0, min: 0, step: 0.05 },
  // Explicit "use the entire dataset (100%)" switch, so "1" in the field above is never
  // ambiguous between the whole set and a single item.
  full_dataset: { type: 'bool', default: false },
  sampling_mode: {
    type: 'enum',
    options: ['unified', 'stratified', 'split_label_stratified'],
    default: 'unified',
  },
  train_sampling_ratio: { type: 'number', default: null, min: 0, max: 1, step: 0.05 },
  test_sampling_ratio: { type: 'number', default: null, min: 0, max: 1, step: 0.05 },
  test_group_offset: { type: 'number', default: 0, min: 0, step: 1 },
  group_by_task: { type: 'bool', default: true },
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
  imagenhub_source: {
    repeat: { type: 'enum', options: ['1', '2', '3'], default: '1' },
    editors: {
      type: 'list[enum]', options: IMAGENHUB_EDITORS, default: PUBLIC_IMAGENMUSEUM_EDITORS,
    },
  },
  editinspector_source: {
    partition: {
      type: 'enum',
      default: 'all',
      options: ['all', 'calibration', 'development', 'confirmation', 'final'],
    },
  },
  dataset: {
    ...SAMPLING_FIELDS,
    // How multiple annotators' scores for the same video are combined into `labels`.
    // mean/median/max/min collapse to one score per dimension; "none" does no aggregation
    // (per-annotator scores kept in raw_scores; Eval scores the judge against each rater,
    // calibration nodes require an aggregated method).
    aggregation_method: {
      type: 'enum', options: ['mean', 'median', 'max', 'min', 'none'], default: 'none',
    },
  },
  preprocessing: {
    artifact_types: { type: 'list[enum]', options: PREPROCESSING_ARTIFACT_TYPES, default: null },
    input_strategy: { type: 'enum', options: ['A', 'B', 'C', 'D', 'E'], default: 'A' },
    cache_policy: {
      type: 'enum', options: ['reuse_if_present', 'force_recompute'], default: 'reuse_if_present',
    },
  },
  unit_labels: {
    path: { type: 'string', default: '' },
  },
  edit_decomposition: {
    boundary_context_seconds: { type: 'number', default: 2.0, min: 0.1 },
    reconcile_tolerance_seconds: { type: 'number', default: 0.1, min: 0 },
    max_sequence_seconds: { type: 'number', default: 30, min: 3 },
    scene_threshold: { type: 'number', default: 27, min: 1 },
    silence_threshold_db: { type: 'number', default: -40 },
    minimum_silence_seconds: { type: 'number', default: 0.5, min: 0.1 },
    extract_artifacts: { type: 'bool', default: true },
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
    modality: { type: 'enum', options: ['text', 'image', 'video'], default: 'text' },
    system: { type: 'text', default: null },
    user_template: { type: 'text', default: null },
    expected_fields: { type: 'list[string]', default: null },
    score_path: { type: 'string', default: 'score_1_to_5' },
    target_dimension: {
      type: 'enum', options: [...HUMAN_DIMENSIONS, 'satisfaction'], default: HUMAN_DIMENSIONS[0],
    },
  },
  area_rubric: {
    rubric: {
      type: 'enum',
      options: [
        'transition_smoothness', 'visual_quality_temporal_stability',
        'pacing_narrative_coherence', 'audio_continuity_av_sync',
      ],
      default: 'transition_smoothness',
    },
  },
  area_judge: {
    boundary_cap: { type: 'number', default: 32, min: 0 },
    shot_cap: { type: 'number', default: 24, min: 0 },
    sequence_cap: { type: 'number', default: 12, min: 0 },
    audio_event_cap: { type: 'number', default: 24, min: 0 },
  },
  area_aggregation: {},
  // engine_kind/model/temperature/concurrency come from a required upstream LM Engine Node's
  // `engine_config` input; the metric comes from a required `judge_spec` input.
  judge: {
    batch_size: { type: 'number', default: 1, min: 1 },
  },
  eval: {},
  // judge_engine/human_engine come from two required upstream LM Engine Nodes;
  // summarizer_engine is required only when use_llm_summarization is enabled.
  // `engine_config` inputs; `judge_result` (a Judge Node's output) supplies the anchor
  // score and metric identity — there's no metric_id param, the metric is a wired
  // artifact same as everywhere else in this node system. `labels` is optional (used
  // only for the secondary tab's judge-vs-human score comparison, not the debate itself).
  cl_adversarial: {
    epsilon: { type: 'number', default: 0.25, min: 0, step: 0.05 },
    max_rounds: { type: 'number', default: 4, min: 1, max: 6 },
    retrieval_enabled: { type: 'bool', default: true },
    batch_size: { type: 'number', default: 1, min: 1 },
    // "" (default) = auto-detect via the ALIGNMENT crosswalk; set only for metrics
    // (M1/M2/M4) with no direct human-dimension mapping.
    human_dimension_override: { type: 'enum', options: ['', ...HUMAN_DIMENSIONS], default: '' },
    // Opt-in: when a real human label exists for an item, convergence requires
    // closing the gap to it, not just round-to-round self-stability. Off by default —
    // changes what the debate optimizes for, so it's a deliberate choice.
    ground_in_human_labels: { type: 'bool', default: false },
    // New nodes default to richer, billable semantic distillation. Saved legacy graphs
    // omit this key and the backend keeps them on deterministic rule-based mode.
    use_llm_summarization: { type: 'bool', default: true },
  },
  cl_rule_tree: {
    max_questions: { type: 'number', default: 5, min: 1 },
    batch_size: { type: 'number', default: 1, min: 1 },
    // "" (default) = auto-detect the human dimension(s) via the ALIGNMENT crosswalk.
    human_dimension_override: { type: 'enum', options: ['', ...HUMAN_DIMENSIONS], default: '' },
    evaluation_mode: {
      type: 'enum', options: ['frozen_holdout', 'grouped_loo_exploratory'], default: 'frozen_holdout',
    },
    validation_fraction: { type: 'number', default: 0.2, min: 0.1, max: 0.5, step: 0.05 },
    split_seed: { type: 'number', default: 0, min: 0 },
  },
  // No params — it just renders the upstream judge_rule report.
  cl_rule_eval: {},
  // No params — frames the upstream metrics_report.
  alignment_report: {},
  cl_semantic_tree: {
    max_questions: { type: 'number', default: 5, min: 1 },
    batch_size: { type: 'number', default: 1, min: 1 },
    prefer_deeper_semantic_tree: { type: 'bool', default: false },
    // "" (default) = auto-detect the human dimension(s) via the ALIGNMENT crosswalk.
    human_dimension_override: { type: 'enum', options: ['', ...HUMAN_DIMENSIONS], default: '' },
    evaluation_mode: {
      type: 'enum', options: ['frozen_holdout', 'grouped_loo_exploratory'], default: 'frozen_holdout',
    },
    validation_fraction: { type: 'number', default: 0.2, min: 0.1, max: 0.5, step: 0.05 },
    split_seed: { type: 'number', default: 0, min: 0 },
  },
  edit_aware_calibration: {
    validation_fraction: { type: 'number', default: 0.2, min: 0.1, max: 0.5, step: 0.05 },
    split_seed: { type: 'number', default: 0, min: 0 },
    bootstrap_repeats: { type: 'number', default: 1000, min: 0 },
  },
  calitree_train: {
    embedding_model: { type: 'string', default: '' },
    prompt_version: {
      type: 'enum',
      options: ['calitree_v1', 'calitree_v2', 'calitree_v3', 'calitree_v4'],
      default: 'calitree_v2',
    },
    max_steps: { type: 'number', default: 3, min: 1, max: 10 },
    merge_acceptance: { type: 'number', default: 0.8, min: 0, max: 1, step: 0.05 },
    similarity_start: { type: 'number', default: 0.9, min: 0, max: 1, step: 0.05 },
    similarity_decay: { type: 'number', default: 0.05, min: 0.01, max: 1, step: 0.01 },
    similarity_floor: { type: 'number', default: 0.7, min: 0, max: 1, step: 0.05 },
    warm_start: { type: 'bool', default: true },
    merge_validation_cap: { type: 'number', default: 6, min: 0 },
    merge_regression_tolerance: {
      type: 'number', default: 0.05, min: 0, max: 1, step: 0.01,
    },
    merge_generalization_floor: {
      type: 'number', default: 0.8, min: 0, max: 1, step: 0.05,
    },
    routing_margin: { type: 'number', default: 0.02, min: 0, max: 1, step: 0.01 },
    min_routing_support: { type: 'number', default: 2, min: 1 },
    singleton_exact_threshold: {
      type: 'number', default: 0.995, min: 0, max: 1, step: 0.001,
    },
    global_min_validation_gain: {
      type: 'number', default: 0, min: 0, max: 1, step: 0.01,
    },
    max_merge_attempts: { type: 'number', default: 20, min: 0 },
    semantic_premerge_levels: { type: 'number', default: 2, min: 0, max: 10 },
    validation_fraction: { type: 'number', default: 0.25, min: 0, max: 0.5, step: 0.05 },
    split_seed: { type: 'number', default: 44, min: 0 },
    run_baselines: { type: 'bool', default: true },
    run_conflict_resolver: { type: 'bool', default: true },
    conflict_min_support: { type: 'number', default: 4, min: 1 },
    conflict_min_gain: { type: 'number', default: 0, min: 0, max: 1, step: 0.01 },
  consensus_min_gain: { type: 'number', default: 0, min: 0, max: 1, step: 0.01 },
  calibration_agreement_filter: {
    type: 'enum', default: 'all', options: ['all', 'unanimous'],
  },
    selective_min_consensus_support: { type: 'number', default: 3, min: 1, max: 3 },
    selective_editor_min_support: { type: 'number', default: 10, min: 1 },
    selective_editor_accuracy_threshold: {
      type: 'number', default: 0.85, min: 0, max: 1, step: 0.01,
    },
    editor_prior_threshold: { type: 'number', default: 0.98, min: 0, max: 1, step: 0.01 },
    editor_prior_min_support: { type: 'number', default: 20, min: 1 },
  },
  rubric_lite_train: {
    rubric_version: {
      type: 'enum',
      default: 'rubric_lite_v1',
      options: [
        'rubric_lite_v1', 'rubric_lite_v2', 'rubric_lite_v3', 'rubric_lite_v4',
        'rubric_lite_v5', 'rubric_lite_v6',
      ],
    },
    max_steps: { type: 'number', default: 3, min: 0, max: 10 },
    feedback_cases_per_bucket: { type: 'number', default: 8, min: 1, max: 50 },
    max_validation_accuracy_drop: {
      type: 'number', default: 0.01, min: 0, max: 0.2, step: 0.01,
    },
    ordinal_accuracy_tolerance: {
      type: 'number', default: 0.01, min: 0, max: 0.2, step: 0.01,
    },
    ordinal_minimum_class_recall: {
      type: 'number', default: 0.1, min: 0, max: 1, step: 0.05,
    },
    validation_fraction: { type: 'number', default: 0.25, min: 0.1, max: 0.5, step: 0.05 },
    split_seed: { type: 'number', default: 44, min: 0 },
    agreement_filter: {
      type: 'enum', default: 'unanimous', options: ['all', 'unanimous'],
    },
    run_initial_baseline: { type: 'bool', default: true },
  },
  rubric_lite_boundary: {
    enabled: { type: 'bool', default: true },
    verifier_version: {
      type: 'enum',
      default: 'rubric_lite_partial_v2',
      options: ['rubric_lite_partial_v2', 'rubric_lite_v1'],
    },
    minimum_ordinal_score: {
      type: 'number', default: 50, min: 0, max: 100, step: 5,
    },
    eligible_base_labels: {
      type: 'list[string]',
      default: ['yes'],
      options: ['no', 'partial', 'yes'],
    },
    decision_policy: {
      type: 'enum',
      default: 'replace',
      options: ['replace', 'partial_only'],
    },
    apply_split: {
      type: 'enum', default: 'all', options: ['all', 'train', 'test'],
    },
  },
  rubric_lite_frozen: {
    model_version: {
      type: 'enum',
      default: 'rubric_lite_v4_imagenhub',
      options: [
        'rubric_lite_v4_imagenhub',
        'rubric_lite_v4_editinspector_cutpoints_v1',
        'rubric_lite_v5_core_completion_experimental',
        'rubric_lite_v6_evidence_ledger_experimental',
      ],
    },
  },
  rubric_lite_fit: {
    selection_objective: {
      type: 'enum',
      default: 'macro_f1',
      options: ['macro_f1', 'accuracy_guarded_partial'],
    },
    minimum_class_recall: {
      type: 'number', default: 0.1, min: 0, max: 1, step: 0.05,
    },
    accuracy_tolerance: {
      type: 'number', default: 0.01, min: 0, max: 0.2, step: 0.01,
    },
    cv_folds: { type: 'number', default: 5, min: 2, max: 10, step: 1 },
    cv_seed: { type: 'number', default: 44, min: 0, step: 1 },
    group_by_task: { type: 'bool', default: true },
  },
  rubric_lite_apply: {},
  calitree_judge: {
    human_review_mode: {
      type: 'enum',
      default: 'off',
      options: ['off', 'selective_policy'],
    },
  },
  calitree_eval: {},
}

export function defaultParamsFor(nodeType: string): Record<string, unknown> {
  const schema = NODE_PARAM_SCHEMAS[nodeType] ?? {}
  const params: Record<string, unknown> = {}
  for (const [key, field] of Object.entries(schema)) {
    params[key] = field.default
  }
  return params
}
