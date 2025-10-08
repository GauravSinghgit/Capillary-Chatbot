import React, { useState } from 'react'

export function Chat() {
  const [messages, setMessages] = useState<{ role: 'user'|'assistant', content: string, sources?: string[] }[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  async function send() {
    const q = input.trim()
    if (!q) return
    setMessages(m => [...m, { role: 'user', content: q }])
    setInput('')
    setLoading(true)
    try {
      const resp = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q })
      })
      const data = await resp.json()
      setMessages(m => [...m, { role: 'assistant', content: data.answer, sources: data.sources }])
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', content: 'Error fetching answer.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 800, margin: '40px auto', fontFamily: 'Inter, system-ui, Arial' }}>
      <h2>Capillary Docs Chatbot</h2>
      <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 16, minHeight: 300 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 600 }}>{m.role === 'user' ? 'You' : 'Assistant'}</div>
            <div style={{ whiteSpace: 'pre-wrap' }}>{m.content}</div>
            {m.sources && m.sources.length > 0 && (
              <div style={{ marginTop: 8, fontSize: 13 }}>
                <div style={{ fontWeight: 600 }}>Sources:</div>
                <ul>
                  {m.sources.map((s, si) => (
                    <li key={si}><a href={s} target="_blank" rel="noreferrer">{s}</a></li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <input value={input} onChange={e => setInput(e.target.value)} placeholder="Ask about Capillary docs..." style={{ flex: 1, padding: 10, borderRadius: 6, border: '1px solid #ccc' }} />
        <button onClick={send} disabled={loading} style={{ padding: '10px 14px' }}>{loading ? 'Thinking...' : 'Send'}</button>
      </div>
    </div>
  )
}
