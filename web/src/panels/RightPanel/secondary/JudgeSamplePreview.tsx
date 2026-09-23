import { mediaUrl } from '../../../api/media'
import { HUMAN_DIMENSIONS } from '../../../nodes/judgeSampleSchema'

// Shared structured preview of one `JudgeSample`-shaped item, used by both the Peanut
// Source Node's secondary tab (raw items, no label) and the Dataset Node's secondary tab
// (sampled items, with their joined human label when one exists). Lifted out of
// SourceSecondaryTab's old inline `ItemPreview` so the two tabs render items identically.
export function JudgeSamplePreview({
  item, label,
}: {
  item: Record<string, unknown>
  // The joined AggregatedHumanRecord for this item id (see judgeSampleSchema.ts's
  // HUMAN_LABEL_SCHEMA). `undefined` when the item has no human annotation — Dataset's
  // `labels` output simply omits unlabeled items, so this is expected, not an error.
  label?: Record<string, unknown>
}) {
  // peanut_eval (JudgeSample) shape.
  const input = (item.input as Record<string, unknown>) ?? {}
  const output = (item.output as Record<string, unknown>) ?? {}
  return (
    <div>
      <h4>{String(item.item_id ?? '')}</h4>
      <div className="item-field"><strong>use_case:</strong> {String(item.use_case ?? '')}</div>
      <div className="item-field"><strong>prompt:</strong> {String(input.user_prompt ?? '')}</div>
      {typeof output.output_video_path === 'string' && output.output_video_path && (
        <div className="item-field">
          <strong>video:</strong>
          <video
            controls preload="metadata" className="item-video"
            src={mediaUrl(output.output_video_path)}
          />
          <div><span className="mono-path">{output.output_video_path}</span></div>
        </div>
      )}
      {typeof input.source_image_path === 'string' && input.source_image_path &&
       typeof output.edited_image_path === 'string' && output.edited_image_path && (
        <div className="calitree-image-pair">
          <figure>
            <img src={mediaUrl(input.source_image_path)} alt="Source" />
            <figcaption>Source</figcaption>
          </figure>
          <figure>
            <img src={mediaUrl(output.edited_image_path)} alt="Edited" />
            <figcaption>Edited</figcaption>
          </figure>
        </div>
      )}
      {label !== undefined && <HumanLabelBlock label={label} />}
      {typeof input.b_roll_captions_excerpt === 'string' && input.b_roll_captions_excerpt && (
        <details>
          <summary>B-roll captions</summary>
          <pre className="json-preview">{input.b_roll_captions_excerpt}</pre>
        </details>
      )}
      {typeof input.a_roll_transcript_text === 'string' && input.a_roll_transcript_text && (
        <details>
          <summary>A-roll transcript</summary>
          <pre className="json-preview">{input.a_roll_transcript_text}</pre>
        </details>
      )}
      {output.assembly_json != null && (
        <details>
          <summary>Assembly JSON</summary>
          <pre className="json-preview">{JSON.stringify(output.assembly_json, null, 2)}</pre>
        </details>
      )}
      <details>
        <summary>Raw JSON</summary>
        <pre className="json-preview">{JSON.stringify(item, null, 2)}</pre>
      </details>
    </div>
  )
}

function HumanLabelBlock({ label }: { label: Record<string, unknown> }) {
  if (typeof label.target_label === 'string') {
    const ratings = (label.ratings as Array<{ sc: number; pq: number }> | undefined) ?? []
    return (
      <div className="human-label-block">
        <div><strong>Human target:</strong> {label.target_label} (median SC {String(label.median_sc)})</div>
        <div>Raters: {ratings.map((rating) => `SC ${rating.sc} / PQ ${rating.pq}`).join(' · ')}</div>
      </div>
    )
  }
  const scores = (label.scores as Record<string, number | null> | undefined) ?? {}
  const rawScores = (label.raw_scores as Record<string, number[]> | undefined) ?? {}
  const nAnnotators = Number(label.n_annotators ?? 0)
  const nComplete = Number(label.n_complete ?? 0)
  // aggregation_method="none" on the Dataset node → no single score per dimension; show each
  // annotator's raw score instead of one aggregate. Detect via the record's `aggregation` tag.
  const unaggregated = label.aggregation === 'none'

  if (unaggregated) {
    // Column per rater (max across dimensions), one row per dimension.
    const nRaters = Math.max(0, ...HUMAN_DIMENSIONS.map((d) => rawScores[d]?.length ?? 0))
    return (
      <div className="human-label-block">
        <div className="item-field">
          <strong>Human label (no aggregation):</strong> {nAnnotators} annotator(s),{' '}
          {nComplete} complete — per-rater scores
        </div>
        <table className="label-score-table">
          <tbody>
            {HUMAN_DIMENSIONS.map((dim) => {
              const vals = rawScores[dim] ?? []
              return (
                <tr key={dim}>
                  <td className="label-dim">{dim}</td>
                  {Array.from({ length: nRaters }).map((_, r) => {
                    const v = vals[r]
                    return (
                      <td
                        key={r}
                        className={`label-score${v == null ? ' label-score-missing' : ''}`}
                      >
                        {v == null ? '—' : v.toFixed(0)}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  }

  return (
    <div className="human-label-block">
      <div className="item-field">
        <strong>Human label:</strong> {nAnnotators} annotator(s), {nComplete} complete
      </div>
      <table className="label-score-table">
        <tbody>
          {HUMAN_DIMENSIONS.map((dim) => {
            const v = scores[dim]
            return (
              <tr key={dim}>
                <td className="label-dim">{dim}</td>
                <td className={`label-score${v == null ? ' label-score-missing' : ''}`}>
                  {v == null ? '—' : v.toFixed(2)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
