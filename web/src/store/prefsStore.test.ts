import { beforeEach, describe, expect, it } from 'vitest'
import { usePrefsStore } from './prefsStore'

beforeEach(() => {
  usePrefsStore.setState({
    leftWidth: 260, rightWidth: 300, bottomHeight: 180, leftCollapsed: false,
  })
})

describe('prefsStore', () => {
  it('setLeftWidth clamps to the [180, 480] range', () => {
    usePrefsStore.getState().setLeftWidth(50)
    expect(usePrefsStore.getState().leftWidth).toBe(180)
    usePrefsStore.getState().setLeftWidth(9999)
    expect(usePrefsStore.getState().leftWidth).toBe(480)
    usePrefsStore.getState().setLeftWidth(300)
    expect(usePrefsStore.getState().leftWidth).toBe(300)
  })

  it('setRightWidth clamps to the [220, 480] range', () => {
    usePrefsStore.getState().setRightWidth(10)
    expect(usePrefsStore.getState().rightWidth).toBe(220)
    usePrefsStore.getState().setRightWidth(9999)
    expect(usePrefsStore.getState().rightWidth).toBe(480)
  })

  it('setBottomHeight clamps to the [80, 480] range', () => {
    usePrefsStore.getState().setBottomHeight(1)
    expect(usePrefsStore.getState().bottomHeight).toBe(80)
    usePrefsStore.getState().setBottomHeight(9999)
    expect(usePrefsStore.getState().bottomHeight).toBe(480)
  })

  it('setLeftCollapsed toggles independently of width', () => {
    usePrefsStore.getState().setLeftWidth(350)
    usePrefsStore.getState().setLeftCollapsed(true)
    expect(usePrefsStore.getState().leftCollapsed).toBe(true)
    expect(usePrefsStore.getState().leftWidth).toBe(350) // unaffected
  })

  it('persists to localStorage under its own key', () => {
    usePrefsStore.getState().setLeftWidth(333)
    const raw = localStorage.getItem('vejudge-panel-prefs')
    expect(raw).toBeTruthy()
    const parsed = JSON.parse(raw as string)
    expect(parsed.state.leftWidth).toBe(333)
  })
})
