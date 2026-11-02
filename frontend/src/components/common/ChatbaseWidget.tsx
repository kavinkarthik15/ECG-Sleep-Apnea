import { useEffect } from 'react'

const CHATBASE_SCRIPT_ID = 'QM-XJ_Y0FuPtdn25tKEwn'
const CHATBASE_SCRIPT_SRC = 'https://www.chatbase.co/embed.min.js'
const CHATBASE_DOMAIN = 'www.chatbase.co'

type ChatbaseFunction = {
  (...args: unknown[]): void
  q?: unknown[][]
  getState?: () => string
}

declare global {
  interface Window {
    chatbase?: ChatbaseFunction
  }
}

let chatbaseLoadPromise: Promise<void> | null = null

function initializeChatbaseQueue() {
  if (window.chatbase?.getState?.() === 'initialized') return

  const queue = ((...args: unknown[]) => {
    queue.q ??= []
    queue.q.push(args)
  }) as ChatbaseFunction

  window.chatbase = new Proxy(queue, {
    get(target, property: string | symbol) {
      if (property === 'q') return target.q
      return (...args: unknown[]) => target(property, ...args)
    },
  })
}

function loadChatbase(): Promise<void> {
  if (chatbaseLoadPromise) return chatbaseLoadPromise

  chatbaseLoadPromise = new Promise((resolve, reject) => {
    initializeChatbaseQueue()
    const existingScript = document.getElementById(CHATBASE_SCRIPT_ID)
    if (existingScript) {
      if (existingScript.getAttribute('data-loaded') === 'true') {
        resolve()
        return
      }
      existingScript.addEventListener('load', () => resolve(), { once: true })
      existingScript.addEventListener('error', () => reject(new Error('Chatbase script failed to load.')), { once: true })
      return
    }

    const script = document.createElement('script') as HTMLScriptElement & { domain?: string }
    script.id = CHATBASE_SCRIPT_ID
    script.src = CHATBASE_SCRIPT_SRC
    script.domain = CHATBASE_DOMAIN
    script.addEventListener('load', () => {
      script.setAttribute('data-loaded', 'true')
      resolve()
    }, { once: true })
    script.addEventListener('error', () => reject(new Error('Chatbase script failed to load.')), { once: true })
    document.body.appendChild(script)
  })

  return chatbaseLoadPromise
}

export function ChatbaseWidget() {
  useEffect(() => {
    void loadChatbase().catch((error: unknown) => {
      console.error('Chatbase widget failed to load.', error)
    })
  }, [])

  return null
}
