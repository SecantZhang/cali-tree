import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { activeGraphStore, activeRunStore } from '../../../store/activeTab'
import { useTabsStore } from '../../../store/tabsStore'
import { DatasetSecondaryTab } from './DatasetSecondaryTab'

// The global test setup (src/test/setup.ts) resets the tabs singleton after every test, so
// each test starts with no tabs — seed() just opens one fresh blank tab.
function seedDatasetNode() {
  useTabsStore.getState().openBlankTab()
  activeGraphStore().getState().addNode('dataset', { x: 0, y: 0 })
  return activeGraphStore().getState().nodes[0]
}

describe('DatasetSecondaryTab', () => {
  it('always shows the collapsible schema reference, even before a run', () => {
    const node = seedDatasetNode()
    render(<DatasetSecondaryTab node={node} />)
    expect(screen.getByText(/Schema — what each sampled item/)).toBeInTheDocument()
    // Both schema tables' field rows are present (item_id appears in both shapes).
    expect(screen.getAllByText('item_id').length).toBeGreaterThanOrEqual(2)
    expect(screen.getByText('output.output_video_path')).toBeInTheDocument()
    // No items yet → the run hint, not a browser.
    expect(screen.getByText(/Run this node to browse/)).toBeInTheDocument()
  })

  it('browses the sampled items and shows a joined human label when present', () => {
    const node = seedDatasetNode()
    activeRunStore().getState().setLastNodeResults({
      [node.id]: {
        status: 'done',
        error: null,
        meta: { n_items: 2, n_raw_items: 5, n_labels: 1 },
        outputs: {
          samples: {
            'prj-a::0::peanut': {
              item_id: 'prj-a::0::peanut', use_case: 'visual montage',
              input: { user_prompt: 'a' }, output: { output_video_path: '' },
            },
            'prj-b::0::peanut': {
              item_id: 'prj-b::0::peanut', use_case: 'speech-driven',
              input: { user_prompt: 'b' }, output: { output_video_path: '' },
            },
          },
          labels: {
            'prj-a::0::peanut': { n_annotators: 2, n_complete: 2, scores: { video_addresses_prompt: 4 } },
          },
        },
      },
    })

    render(<DatasetSecondaryTab node={node} />)
    // Both items listed.
    expect(screen.getByText('prj-a::0::peanut')).toBeInTheDocument()
    expect(screen.getByText('prj-b::0::peanut')).toBeInTheDocument()

    // Selecting the labeled item shows its human-label block.
    fireEvent.click(screen.getByText('prj-a::0::peanut'))
    expect(screen.getByText(/2 annotator\(s\), 2 complete/)).toBeInTheDocument()

    // Selecting the unlabeled item shows the preview but no label block.
    fireEvent.click(screen.getByText('prj-b::0::peanut'))
    expect(screen.queryByText(/annotator\(s\)/)).toBeNull()
  })
})
