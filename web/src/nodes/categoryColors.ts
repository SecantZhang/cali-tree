export const CATEGORY_COLORS: Record<string, string> = {
  node_db: 'var(--node-db)',
  node_lm_engine: 'var(--node-lm-engine)',
  node_preprocessing: 'var(--node-preprocessing)',
  node_vejudge: 'var(--node-vejudge)',
  node_eval: 'var(--node-eval)',
  node_calibration: 'var(--node-calibration)',
}

// Display order + label for the Nodes-tab palette's category grouping (interface.md's
// category table) — categories not listed here fall back to their raw key, sorted after.
export const CATEGORY_LABELS: Record<string, string> = {
  node_db: 'Data',
  node_lm_engine: 'LM Engine',
  node_preprocessing: 'Preprocessing',
  node_vejudge: 'Judge',
  node_eval: 'Eval',
  node_calibration: 'Calibration',
}

export const CATEGORY_ORDER: string[] = [
  'node_db', 'node_lm_engine', 'node_preprocessing', 'node_vejudge', 'node_eval',
  'node_calibration',
]

// Sub-folders shown *within* a category in the palette (see NodeExecutor.subcategory).
// Calibration splits by role: Agent (debate producers) → Model (fitters: trees + other
// calibrators). Nodes with no subcategory render flat under their category.
export const SUBCATEGORY_LABELS: Record<string, string> = {
  agent: 'Agent Calibration',
  model: 'Model Calibration',
}

export const SUBCATEGORY_ORDER: string[] = ['agent', 'model']
