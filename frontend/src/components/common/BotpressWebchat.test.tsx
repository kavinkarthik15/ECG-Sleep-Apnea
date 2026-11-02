import { render, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { BotpressWebchat } from './BotpressWebchat'

const injectScriptId = 'botpress-webchat-inject'
const configScriptId = 'botpress-webchat-config'

afterEach(() => {
  document.getElementById(injectScriptId)?.remove()
  document.getElementById(configScriptId)?.remove()
})

describe('BotpressWebchat', () => {
  it('loads the embed scripts once with the configured sources', async () => {
    const firstRender = render(<BotpressWebchat />)
    const secondRender = render(<BotpressWebchat />)

    const scripts = [...document.head.querySelectorAll('script')]
    expect(scripts.filter((script) => script.id === injectScriptId)).toHaveLength(1)
    expect(scripts.filter((script) => script.id === configScriptId)).toHaveLength(0)

    const injectScript = document.getElementById(injectScriptId) as HTMLScriptElement | null
    expect(injectScript?.src).toBe('https://cdn.botpress.cloud/webchat/v5.0/inject.js')

    injectScript?.dispatchEvent(new Event('load'))

    const configScript = await waitFor(() => {
      const script = document.getElementById(configScriptId)
      expect(script).not.toBeNull()
      return script as HTMLScriptElement | null
    })
    expect(configScript?.src).toBe('https://files.bpcontent.cloud/2026/11/01/10/20261101104205-YBJ2JSH3.js')
    expect(configScript?.defer).toBe(true)

    firstRender.unmount()
    secondRender.unmount()
    render(<BotpressWebchat />)

    expect(document.querySelectorAll(`#${injectScriptId}`)).toHaveLength(1)
    expect(document.querySelectorAll(`#${configScriptId}`)).toHaveLength(1)
  })
})
