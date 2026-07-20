// Shared by the Rule/Tree and Rule Comparison secondary tabs: turns a decision-tree split
// feature name into a hover tooltip so the tree diagram is self-explanatory without the raw
// text. Two feature-naming schemes are supported: the CART tree's positional `qN` (looked up
// in the mined bank) and the semantic tree's concept-labeled features (looked up in the
// payload's `feature_labels` map, which wins when present).
interface BankEntry {
  question: string
  raises_score_when: string
}

export function treeFeatureTooltip(
  bank: BankEntry[],
  featureLabels?: Record<string, string>,
): (feature: string) => string | undefined {
  return (feature) => {
    if (featureLabels && featureLabels[feature]) return featureLabels[feature]
    const m = /^q(\d+)$/.exec(feature)
    if (m) {
      const q = bank[Number(m[1]) - 1]
      return q ? `q${m[1]}: ${q.question} (raises when ${q.raises_score_when})` : undefined
    }
    if (feature === 'base_score') return "the judge's own 1–5 score"
    return undefined
  }
}
