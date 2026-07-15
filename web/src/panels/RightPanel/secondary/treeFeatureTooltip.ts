// Shared by the Rule/Tree and Rule Comparison secondary tabs: turns a decision-tree split
// feature name (`base_score`, `q1`, `q2`, …) into a hover tooltip that spells out the mined
// rule behind a `qN` feature, so the tree diagram is self-explanatory without the raw text.
interface BankEntry {
  question: string
  raises_score_when: string
}

export function treeFeatureTooltip(
  bank: BankEntry[],
): (feature: string) => string | undefined {
  return (feature) => {
    const m = /^q(\d+)$/.exec(feature)
    if (m) {
      const q = bank[Number(m[1]) - 1]
      return q ? `q${m[1]}: ${q.question} (raises when ${q.raises_score_when})` : undefined
    }
    if (feature === 'base_score') return "the judge's own 1–5 score"
    return undefined
  }
}
