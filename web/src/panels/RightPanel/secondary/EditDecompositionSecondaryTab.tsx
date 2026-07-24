import { useState } from 'react'
import { mediaUrl } from '../../../api/media'
import { useActiveRunStore } from '../../../store/activeTab'
import type { VeNode } from '../../../store/graphStore'
import { DataValueView } from './DataValueView'

interface Artifact {
  kind?: string
  path?: string
  media_type?: string
}

interface Unit {
  unit_id?: string
  unit_type?: string
  start_seconds?: number
  end_seconds?: number
  artifacts?: Artifact[]
  measurements?: Record<string, unknown>
}

interface Manifest {
  evidence_hash?: string
  warnings?: string[]
  video_metadata?: Record<string, unknown>
  units?: Unit[]
}

export function EditDecompositionSecondaryTab({ node }: { node: VeNode }) {
  const result = useActiveRunStore((s) => s.lastNodeResults[node.id])
  const bundle = result?.outputs?.evidence_bundle as {
    manifests?: Record<string, Manifest>
  } | undefined
  const manifests = bundle?.manifests ?? {}
  const itemIds = Object.keys(manifests)
  const [selectedItem, setSelectedItem] = useState<string | null>(null)
  const [selectedUnitId, setSelectedUnitId] = useState<string | null>(null)
  if (!itemIds.length) {
    return <p className="empty-hint">Run decomposition to inspect cached evidence units.</p>
  }
  const itemId = selectedItem && manifests[selectedItem] ? selectedItem : itemIds[0]
  const manifest = manifests[itemId]
  const units = manifest.units ?? []
  const unit = units.find((value) => value.unit_id === selectedUnitId) ?? units[0]
  const media = unit?.artifacts?.find((artifact) =>
    artifact.kind === 'short_clip' || artifact.kind === 'keyframe')
  const counts = units.reduce<Record<string, number>>((acc, value) => {
    const key = value.unit_type ?? 'unknown'
    acc[key] = (acc[key] ?? 0) + 1
    return acc
  }, {})
  return (
    <div>
      <div className="secondary-summary">
        <div><strong>Items:</strong> {itemIds.length}</div>
        <div><strong>Units:</strong> {units.length}</div>
        <div><strong>By type:</strong> {Object.entries(counts).map(([k, v]) => `${k}=${v}`).join(', ')}</div>
      </div>
      <div className="secondary-split">
        <ul className="dataset-item-list secondary-item-list">
          {itemIds.map((id) => <li key={id} className={id === itemId ? 'active' : ''}
            onClick={() => { setSelectedItem(id); setSelectedUnitId(null) }}>{id}</li>)}
        </ul>
        <div className="rationale-view">
          {manifest.warnings?.map((warning) =>
            <p key={warning} className="rationale-error">{warning}</p>)}
          <div className="item-field"><strong>Evidence:</strong> {manifest.evidence_hash}</div>
          <DataValueView value={manifest.video_metadata} />
          <select value={unit?.unit_id ?? ''} onChange={(event) => setSelectedUnitId(event.target.value)}>
            {units.map((value) => <option key={value.unit_id} value={value.unit_id}>
              {value.unit_type} · {Number(value.start_seconds ?? 0).toFixed(2)}–
              {Number(value.end_seconds ?? 0).toFixed(2)}s
            </option>)}
          </select>
          {media?.path && media.media_type?.startsWith('image/') && (
            <img className="item-video" src={mediaUrl(media.path)} alt={unit?.unit_id ?? 'evidence'} />
          )}
          {media?.path && !media.media_type?.startsWith('image/') && (
            <video controls preload="metadata" className="item-video" src={mediaUrl(media.path)} />
          )}
          <DataValueView value={unit} />
        </div>
      </div>
    </div>
  )
}
