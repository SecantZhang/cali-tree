// Static mirror of the backend's socket shapes (vejudge/interface/server/registry.py's
// NODE_EXECUTORS).

export type SocketType =
  | 'raw_dataset' | 'raw_labels' | 'samples' | 'labels' | 'engine_config' | 'judge_spec' | 'judge_result'
  | 'metrics_report' | 'calibration_results' | 'general_calibration' | 'judge_rule'
  | 'evidence_bundle' | 'area_rubric_spec' | 'area_judge_result'
  | 'decomposition_features' | 'unit_labels' | 'active_labeling_report'
  | 'prompt_tree' | 'calitree_report'
  | 'rubric_calibrator'

export const SOCKET_COLORS: Record<SocketType, string> = {
  raw_dataset: 'var(--node-db)',
  raw_labels: 'var(--node-db)',
  samples: 'var(--node-db)',
  labels: 'var(--node-db)',
  engine_config: 'var(--node-lm-engine)',
  judge_spec: 'var(--node-vejudge)',
  judge_result: 'var(--node-vejudge)',
  metrics_report: 'var(--node-eval)',
  calibration_results: 'var(--node-calibration)',
  general_calibration: 'var(--node-calibration)',
  judge_rule: 'var(--node-calibration)',
  evidence_bundle: 'var(--node-preprocessing)',
  area_rubric_spec: 'var(--node-vejudge)',
  area_judge_result: 'var(--node-vejudge)',
  decomposition_features: 'var(--node-calibration)',
  unit_labels: 'var(--node-db)',
  active_labeling_report: 'var(--node-calibration)',
  prompt_tree: 'var(--node-calibration)',
  calitree_report: 'var(--node-calibration)',
  rubric_calibrator: 'var(--node-calibration)',
}

// A representative example payload per socket type, shown (collapsed, expandable) in the
// Inputs/Outputs schema header so the contract reads as real JSON with its subfields, not just
// a bare type name. Hand-maintained per socket *type* (like SOCKET_COLORS) — a brand-new type
// simply has no example yet and falls back to name+type only. Kept faithful to the backend
// shapes (JudgeSample, AggregatedHumanRecord, the eval report, etc.), abbreviated for clarity.
export const SOCKET_EXAMPLES: Partial<Record<SocketType, unknown>> = {
  // A source node's full item pool: item_id -> JudgeSample (dl_peanut_eval.curate shape).
  raw_dataset: {
    'travel_vlog::0::modelX': {
      item_id: 'travel_vlog::0::modelX',
      project: 'travel_vlog',
      prompt_idx: 0,
      model: 'modelX',
      use_case: 'social_promo',
      input: {
        asset_filepaths: ['assets/clip_01.mp4', 'assets/clip_02.mp4', 'assets/music.mp3'],
        user_prompt: 'Make a 30s upbeat travel promo with captions.',
        target_duration: 30,
        a_roll_transcript_text: 'Welcome to sunny Lisbon…',
        prompt_index: 0,
      },
      output: {
        output_video_path: 'rendered/travel_vlog/0/modelX.mp4',
        assembly_json: { tracks: [{ clips: [{ src: 'clip_01.mp4', in: 0.0, out: 4.2 }] }] },
      },
    },
  },
  // The Dataset node's sampled subset — same JudgeSample shape as raw_dataset, fewer items.
  samples: {
    'travel_vlog::0::modelX': {
      item_id: 'travel_vlog::0::modelX',
      use_case: 'social_promo',
      input: { user_prompt: 'Make a 30s upbeat travel promo…', target_duration: 30 },
      output: { output_video_path: 'rendered/travel_vlog/0/modelX.mp4' },
    },
  },
  // Human annotations: item_id -> AggregatedHumanRecord (per-rater raw_scores kept alongside
  // the mean in `scores`).
  labels: {
    'travel_vlog::0::modelX': {
      item_id: 'travel_vlog::0::modelX',
      project: 'travel_vlog',
      use_case: 'social_promo',
      n_annotators: 3,
      n_complete: 3,
      // Set by the Dataset node's aggregation_method: mean (default) / median / max / min, or
      // "none" — then `scores` is null and consumers read the per-annotator `raw_scores`.
      aggregation: 'mean',
      scores: { story_flow_visuals: 3.67, video_addresses_prompt: 4.0 },
      score_counts: { story_flow_visuals: 3, video_addresses_prompt: 3 },
      raw_scores: { story_flow_visuals: [3, 4, 4], video_addresses_prompt: [4, 4, 4] },
    },
  },
  unit_labels: [{
    item_id: 'travel_vlog::0::modelX',
    unit_id: 'edit_boundary-0004-abcd1234',
    rubric_id: 'transition_smoothness',
    rating: 2,
    severity: 'major',
    comment: 'The voiceover is cut mid-word.',
  }],
  evidence_bundle: {
    schema_version: 'evidence-bundle-v1',
    preprocessing_config_hash: 'abc123',
    manifests: {
      'travel_vlog::0::modelX': {
        evidence_hash: 'evidence-sha256',
        video_metadata: { duration_seconds: 30, fps: 30, has_audio: true },
        units: [{
          unit_id: 'edit_boundary-0004-abcd1234',
          unit_type: 'edit_boundary',
          start_seconds: 10,
          end_seconds: 14,
          applicable_rubrics: ['transition_smoothness'],
        }],
      },
    },
  },
  area_rubric_spec: {
    kind: 'area',
    rubric_id: 'transition_smoothness',
    unit_types: ['edit_boundary'],
    version: 'area-transition-v1',
  },
  area_judge_result: {
    'travel_vlog::0::modelX': {
      rubric_id: 'transition_smoothness',
      selection: { selected: 8, total: 8, coverage: 1 },
      units: [{ unit_id: 'edit_boundary-0004-abcd1234', score: 2, severity: 'major' }],
    },
  },
  decomposition_features: {
    'travel_vlog::0::modelX': {
      features: { 'area:transition_smoothness:p20': 2.4 },
    },
  },
  active_labeling_report: {
    items: [{
      item_id: 'travel_vlog::0::modelX',
      priority: 0.92,
      reasons: ['wide_calibration_interval'],
    }],
  },
  rubric_calibrator: {
    version: 'rubric-lite-cutpoints-v1',
    feature: 'minimum_visible_evidence_score',
    thresholds: { no_partial: 25.000001, partial_yes: 75.000001 },
    selection_objective: 'macro_f1',
    uses_editor_identity: false,
    uses_instruction_features: false,
  },
  // An LM Engine node's config.
  engine_config: {
    engine_kind: 'openai_compat',
    model: 'gpt-4.1',
    temperature: 0.0,
    max_tokens: 1024,
  },
  // A Judge Prompt node's metric identity as data: a builtin M1–M6 preset…
  judge_spec: {
    kind: 'builtin',
    metric_id: 'M3',
    modality: 'text',
    label: 'M3',
    // …or a custom judge: { kind: "custom", spec_id, prompt_template, target_dimension, modality }
  },
  // A Judge node's output: item_id -> metric -> parsed/raw judge output.
  judge_result: {
    'travel_vlog::0::modelX': {
      M3: {
        parsed: {
          overall_editing_score: 4,
          rationale: 'Cuts are on-beat; one abrupt voiceover cutoff near 0:12.',
          segments: [{ start: 0.0, end: 6.0, score: 4 }],
        },
        raw: '{"overall_editing_score": 4, …}',
      },
    },
  },
  // An Eval node's report: per-dimension agreement + the inter-rater human ceiling + raw rows.
  metrics_report: {
    n_items: 13,
    n_aligned_rows: 13,
    per_dimension: {
      story_flow_visuals: { srcc: 0.62, plcc: 0.58, krcc: 0.49, qwk: 0.55, mae: 0.7, n: 13 },
    },
    human_ceiling: {
      story_flow_visuals: { self_mae: 0.5, pairwise_mae: 0.8, n_items: 13, n_ratings: 39 },
    },
    rows: [{ item_id: 'travel_vlog::0::modelX', dimension: 'story_flow_visuals', human: 3.67, judge: 4 }],
  },
  // An adversarial-debate node's per-item calibrated results.
  calibration_results: {
    'travel_vlog::0::modelX': {
      calibrated_score: 3.8,
      optimized_prompt: 'Weigh abrupt voiceover cutoffs more heavily than visual ones.',
      distilled_reasoning: 'Human penalized the 0:12 cutoff the judge overlooked.',
      transcript: [
        { role: 'judge', text: 'I score this 4/5…' },
        { role: 'human_proxy', text: 'The abrupt cutoff should drop it to 3…' },
      ],
    },
  },
  // A dataset-wide (item-independent) calibration note.
  general_calibration: {
    corpus_note: 'Across this corpus, raters penalize abrupt voiceover cutoffs more than visual ones.',
  },
  // A Rule/Semantic Tree node's fitted report: mined rules + the tree + a held-out verdict.
  judge_rule: {
    rule_bank: [
      { id: 'r1', question: 'Is there an abrupt voiceover cutoff?', concept: 'temporal_consistency' },
    ],
    tree: { feature: 'base_score', threshold: 3.5, left: { leaf: 2.5 }, right: { leaf: 4.1 } },
    mae: { base: 0.9, bias: 0.8, rules_in_sample: 0.5, rules_loo: 0.7 },
    verdict: 'Rules beat a plain bias correction held-out (LOO MAE 0.7 < 0.8).',
  },
}

export interface NodeTypeSockets {
  input: Record<string, SocketType>
  output: Record<string, SocketType>
}

export const NODE_SOCKETS: Record<string, NodeTypeSockets> = {
  peanut_source: { input: {}, output: { raw_dataset: 'raw_dataset' } },
  coconut_source: { input: {}, output: { raw_dataset: 'raw_dataset' } },
  grapenut_source: { input: {}, output: { raw_dataset: 'raw_dataset' } },
  vebench_source: { input: {}, output: { raw_dataset: 'raw_dataset' } },
  imagenhub_source: {
    input: {},
    output: { raw_dataset: 'raw_dataset', raw_labels: 'raw_labels' },
  },
  editinspector_source: {
    input: {},
    output: { raw_dataset: 'raw_dataset', raw_labels: 'raw_labels' },
  },
  // `raw_dataset` is a distinct type from `samples` specifically so a source's raw
  // output can never be wired directly into a Judge node — sampling is always explicit.
  // `labels` is looked up by item id against this node's own sampled items (not
  // independently re-sampled), so judge results and human labels always describe the
  // same items by construction. The sampled-item output is named `samples`, not
  // `dataset` — that name collided with the node's own name and its sibling `labels`
  // output, making the two easy to conflate.
  dataset: {
    input: { raw_dataset: 'raw_dataset', raw_labels: 'raw_labels' },
    output: { samples: 'samples', labels: 'labels' },
  },
  preprocessing: { input: { samples: 'samples' }, output: { samples: 'samples' } },
  unit_labels: { input: {}, output: { unit_labels: 'unit_labels' } },
  edit_decomposition: {
    input: { samples: 'samples' },
    output: { evidence_bundle: 'evidence_bundle' },
  },
  lm_engine: { input: {}, output: { engine_config: 'engine_config' } },
  // A metric is now a wired artifact, not a dropdown: the Judge Prompt node emits a
  // `judge_spec` (a builtin M1-M6 preset, or a custom free-text judge) that the generic
  // Judge node consumes alongside samples + engine.
  judge_prompt: { input: {}, output: { judge_spec: 'judge_spec' } },
  area_rubric: { input: {}, output: { area_rubric_spec: 'area_rubric_spec' } },
  area_judge: {
    input: {
      samples: 'samples', evidence_bundle: 'evidence_bundle',
      engine_config: 'engine_config', area_rubric_spec: 'area_rubric_spec',
    },
    output: { area_judge_result: 'area_judge_result' },
  },
  area_aggregation: {
    input: { area_judge_result: 'area_judge_result', unit_labels: 'unit_labels' },
    output: {
      judge_result: 'judge_result', decomposition_features: 'decomposition_features',
    },
  },
  judge: {
    input: {
      samples: 'samples', engine_config: 'engine_config', judge_spec: 'judge_spec',
      // Optional: a cl_adversarial node's per-item calibrated results. When wired, each
      // item's own optimized_prompt is injected for that item's judge call only.
      calibration: 'calibration_results',
      // Optional: a cl_adversarial node's item-independent corpus note, applied to every
      // item's judge call (dataset-wide).
      general_calibration: 'general_calibration',
    },
    output: { judge_result: 'judge_result' },
  },
  // One generic Eval node: it auto-scopes to whatever dimensions the incoming judge_result
  // covers (builtin metric via ALIGNMENT, or a custom judge's carried target dimension), so
  // each per-metric Judge path feeds straight into its own Eval node.
  eval: {
    input: { judge_result: 'judge_result', labels: 'labels' },
    output: { metrics_report: 'metrics_report' },
  },
  // A bounded judge-vs-human-proxy debate over a dataset — produces a per-item
  // calibrated result (its own transcript, distilled reasoning, and an `optimized_prompt`
  // addendum), not one aggregate prompt for the whole dataset. `labels` is optional (used
  // only for the secondary tab's judge-vs-human score comparison).
  cl_adversarial: {
    input: {
      samples: 'samples', judge_result: 'judge_result', labels: 'labels',
      judge_engine: 'engine_config', human_engine: 'engine_config',
      summarizer_engine: 'engine_config',
    },
    output: {
      calibration_results: 'calibration_results',
      general_calibration: 'general_calibration',
    },
  },
  // Mines reusable decision rules from an upstream cl_adversarial node's debates, has an
  // independent critic answer them per item, and fits a decision tree [base + booleans]
  // -> human score. Fit+report (in-sample + LOO MAE); terminal `judge_rule` output.
  cl_rule_tree: {
    input: {
      samples: 'samples', calibration_results: 'calibration_results', labels: 'labels',
      critic_engine: 'engine_config',
    },
    output: { judge_rule: 'judge_rule' },
  },
  // A standalone eval node that re-surfaces a Rule/Tree Calibration node's `judge_rule`
  // report — the four-way MAE table (in-sample + held-out LOO), the mined rule bank, the
  // fitted tree, and a verdict on whether the rules beat a plain bias correction held-out.
  // Pure display (makes no calls); mirrors the Eval node's read-a-report role.
  cl_rule_eval: {
    input: { judge_rule: 'judge_rule' },
    output: { comparison: 'metrics_report' },
  },
  // Frames an Eval node's metrics_report as SRCC/PLCC/KRCC + human ceiling vs published
  // VE-Bench baselines. Pure display (node_eval), like cl_rule_eval.
  alignment_report: {
    input: { metrics_report: 'metrics_report' },
    output: { comparison: 'metrics_report' },
  },
  // Ontology-weighted semantic decision tree — same Model Calibration fitter contract as
  // cl_rule_tree (splits are concept-labeled and importance-weighted; see ontology.py).
  cl_semantic_tree: {
    input: {
      samples: 'samples', calibration_results: 'calibration_results', labels: 'labels',
      critic_engine: 'engine_config',
    },
    output: { judge_rule: 'judge_rule' },
  },
  edit_aware_calibration: {
    input: {
      samples: 'samples', judge_result: 'judge_result', labels: 'labels',
      decomposition_features: 'decomposition_features', unit_labels: 'unit_labels',
    },
    output: {
      judge_result: 'judge_result', judge_rule: 'judge_rule',
      active_labeling_report: 'active_labeling_report',
    },
  },
  calitree_train: {
    input: {
      samples: 'samples', labels: 'labels',
      judge_engine: 'engine_config', optimizer_engine: 'engine_config',
    },
    output: { prompt_tree: 'prompt_tree', calitree_report: 'calitree_report' },
  },
  rubric_lite_train: {
    input: {
      samples: 'samples', labels: 'labels',
      judge_engine: 'engine_config', optimizer_engine: 'engine_config',
    },
    output: { prompt_tree: 'prompt_tree', calitree_report: 'calitree_report' },
  },
  rubric_lite_boundary: {
    input: {
      samples: 'samples',
      judge_result: 'judge_result',
      judge_engine: 'engine_config',
    },
    output: { judge_result: 'judge_result' },
  },
  rubric_lite_frozen: {
    input: {},
    output: { prompt_tree: 'prompt_tree' },
  },
  calitree_judge: {
    input: {
      samples: 'samples', prompt_tree: 'prompt_tree', judge_engine: 'engine_config',
    },
    output: { judge_result: 'judge_result' },
  },
  calitree_eval: {
    input: { judge_result: 'judge_result', labels: 'labels', samples: 'samples' },
    output: { metrics_report: 'metrics_report' },
  },
}

// Static mirror of the backend's NodeExecutor.multi_input_sockets: input sockets that
// accept fan-in (multiple incoming edges), keyed by node type. The Dataset node merges
// several source nodes this way. Everything else stays one-edge-only.
export const MULTI_INPUT_SOCKETS: Record<string, string[]> = {
  dataset: ['raw_dataset', 'raw_labels'],
  area_aggregation: ['area_judge_result'],
  edit_aware_calibration: ['judge_result'],
}

export function isMultiInputSocket(
  nodeType: string | undefined,
  socket: string | null | undefined,
): boolean {
  if (!nodeType || !socket) return false
  return (MULTI_INPUT_SOCKETS[nodeType] ?? []).includes(socket)
}

export function isValidSocketConnection(
  sourceNodeType: string | undefined,
  sourceHandle: string | null | undefined,
  targetNodeType: string | undefined,
  targetHandle: string | null | undefined,
): boolean {
  if (!sourceNodeType || !targetNodeType || !sourceHandle || !targetHandle) return false
  const sourceSocket = NODE_SOCKETS[sourceNodeType]?.output[sourceHandle]
  const targetSocket = NODE_SOCKETS[targetNodeType]?.input[targetHandle]
  return !!sourceSocket && !!targetSocket && sourceSocket === targetSocket
}
