import { render } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { ChatbaseWidget } from './ChatbaseWidget'

const scriptId = 'QM-XJ_Y0FuPtdn25tKEwn'

afterEach(() => {
  document.getElementById(scriptId)?.remove()
})

describe('ChatbaseWidget', () => {
  it('injects the Chatbase script once with the public embed configuration', () => {
    const firstRender = render(<ChatbaseWidget />)
    const secondRender = render(<ChatbaseWidget />)

    const scripts = document.querySelectorAll(`#${scriptId}`)
    expect(scripts).toHaveLength(1)
    const script = scripts[0] as HTMLScriptElement
    expect(script.src).toBe('https://www.chatbase.co/embed.min.js')
    expect((script as HTMLScriptElement & { domain?: string }).domain).toBe('www.chatbase.co')

    script.dispatchEvent(new Event('load'))
    firstRender.unmount()
    secondRender.unmount()
  })
})
