import { useEffect } from 'react'

const INJECT_SCRIPT_ID = 'botpress-webchat-inject'
const CONFIG_SCRIPT_ID = 'botpress-webchat-config'
const INJECT_SCRIPT_SRC = 'https://cdn.botpress.cloud/webchat/v5.0/inject.js'
const CONFIG_SCRIPT_SRC = 'https://files.bpcontent.cloud/2026/11/01/10/20261101104205-YBJ2JSH3.js'

let webchatScriptsPromise: Promise<void> | null = null

function loadScript(id: string, src: string, defer = false): Promise<void> {
  const existingScript = document.getElementById(id)
  if (existingScript) {
    if (existingScript.getAttribute('data-loaded') === 'true') return Promise.resolve()
    return new Promise((resolve, reject) => {
      existingScript.addEventListener('load', () => resolve(), { once: true })
      existingScript.addEventListener('error', () => reject(new Error(`Failed to load ${src}`)), { once: true })
    })
  }

  const script = document.createElement('script')
  script.id = id
  script.src = src
  script.defer = defer

  const loaded = new Promise<void>((resolve, reject) => {
    script.addEventListener('load', () => {
      script.setAttribute('data-loaded', 'true')
      resolve()
    }, { once: true })
    script.addEventListener('error', () => reject(new Error(`Failed to load ${src}`)), { once: true })
  })

  document.head.appendChild(script)
  return loaded
}

function loadBotpressWebchat(): Promise<void> {
  if (!webchatScriptsPromise) {
    webchatScriptsPromise = loadScript(INJECT_SCRIPT_ID, INJECT_SCRIPT_SRC)
      .then(() => loadScript(CONFIG_SCRIPT_ID, CONFIG_SCRIPT_SRC, true))
  }
  return webchatScriptsPromise
}

export function BotpressWebchat() {
  useEffect(() => {
    void loadBotpressWebchat().catch((error: unknown) => {
      console.error('Botpress Webchat failed to load.', error)
    })
  }, [])

  return null
}
