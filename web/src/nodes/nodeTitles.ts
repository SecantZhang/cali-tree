// Human-readable node titles keyed by node type — the single authority, shared by the
// top-bar RunProgress bars and the LM Engine secondary tab's "feeds" list (and anywhere
// else that needs to name a node by its type). Falls back to the raw type string when a
// type isn't listed (e.g. a future node type not yet added here).
export const NODE_TITLE_FOR_TYPE: Record<string, string> = {
  peanut_source: 'Peanut Source',
  coconut_source: 'Coconut Source',
  grapenut_source: 'Grapenut Source',
  vebench_source: 'VE-Bench Source',
  imagenhub_source: 'ImagenHub Source',
  editinspector_source: 'EditInspector Source',
  dataset: 'Dataset',
  preprocessing: 'Preprocessing',
  unit_labels: 'Human Unit Labels',
  edit_decomposition: 'Edit Decomposition',
  lm_engine: 'LM Engine',
  judge_prompt: 'Judge Prompt',
  judge: 'Judge',
  area_rubric: 'Area Rubric Spec',
  area_judge: 'Area Judge',
  area_aggregation: 'Area Aggregation',
  eval: 'Eval',
  cl_rule_eval: 'Rule Comparison',
  alignment_report: 'Alignment Report',
  cl_adversarial: 'Adversarial Calibration',
  cl_rule_tree: 'Rule/Tree Calibration',
  cl_semantic_tree: 'Semantic Tree Calibration',
  edit_aware_calibration: 'Edit-Aware Calibration',
  calitree_train: 'Cali-Tree Train',
  calitree_judge: 'Cali-Tree Judge',
  calitree_eval: 'Cali-Tree Eval',
  rubric_lite_train: 'Rubric-Lite Train',
  rubric_lite_boundary: 'Partial Boundary Verifier',
  rubric_lite_frozen: 'Frozen Rubric-Lite',
  rubric_lite_fit: 'Rubric-Lite Fit',
  rubric_lite_apply: 'Rubric-Lite Apply',
}

export function nodeTitle(type: string | undefined): string {
  return (type && NODE_TITLE_FOR_TYPE[type]) || type || 'node'
}
