export const CATEGORY_COLORS: Record<string, string> = {
  node_db: 'var(--node-db)',
  node_preprocessing: 'var(--node-preprocessing)',
  node_vejudge: 'var(--node-vejudge)',
  node_eval: 'var(--node-eval)',
}

// Display order + label for the Nodes-tab palette's category grouping (interface.md's
// category table) — categories not listed here fall back to their raw key, sorted after.
export const CATEGORY_LABELS: Record<string, string> = {
  node_db: 'Data',
  node_preprocessing: 'Preprocessing',
  node_vejudge: 'Judge',
  node_eval: 'Eval',
}

export const CATEGORY_ORDER: string[] = ['node_db', 'node_preprocessing', 'node_vejudge', 'node_eval']
