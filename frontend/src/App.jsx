import { useState } from 'react'
const API = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export function sanitizeFilters(filters) {
    if (!filters || typeof filters !== 'object') return undefined
    const cleaned = {}
    for (const [key, value] of Object.entries(filters)) {
        if (value === '' || value === undefined || value === null) {
            continue
        }
        if (['bhk', 'min_price', 'max_price'].includes(key)) {
            const num = Number(value)
            cleaned[key] = isNaN(num) ? value : num
        } else {
            cleaned[key] = value
        }
    }
    return Object.keys(cleaned).length > 0 ? cleaned : undefined
}
export default function App() {
    const [provider, setProvider] = useState('openai'), [input, setInput] = useState('')
    const [messages, setMessages] = useState([{ role: 'assistant', content: 'Hello! Tell me your preferred location, budget and BHK.' }])
    const [properties, setProperties] = useState([]), [busy, setBusy] = useState(false), [selected, setSelected] = useState(null), [notice, setNotice] = useState('')
    const [form, setForm] = useState({ name: '', phone: '', message: 'I am interested in this property.', consent: false })
    async function send(e) {
        e.preventDefault(); if (!input.trim() || busy) return
        const msg = { role: 'user', content: input.trim() }, history = messages.slice(-8); setMessages(p => [...p, msg]); setInput(''); setBusy(true)
        try { const r = await fetch(`${API}/api/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: msg.content, history, provider }) }); const d = await r.json(); if (!r.ok) throw Error(d.detail || 'Search failed'); setMessages(p => [...p, { role: 'assistant', content: d.assistant_message || 'Search complete.' }]); setProperties(d.properties || []) }
        catch (err) { setMessages(p => [...p, { role: 'assistant', content: `Search error: ${err.message}` }]) } finally { setBusy(false) }
    }
    async function submit(e) { e.preventDefault(); try { const r = await fetch(`${API}/api/enquiries`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...form, property_id: selected?.property_id }) }); const d = await r.json(); if (!r.ok) throw Error(d.detail || 'Submission failed'); setNotice(`Enquiry submitted. Reference ${d.enquiry_id}`); setSelected(null); setForm({ name: '', phone: '', message: 'I am interested in this property.', consent: false }) } catch (err) { setNotice(err.message) } }
    return <div className="shell"><header><div className="logo">⌂</div><div><b>EstateAI</b><small>Real Estate Assistant</small></div><span className="topright">● Demo environment</span></header>
        <main><section className="chat panel"><div className="heading"><div><h2>Property assistant</h2><p>Search using everyday language</p></div><span className="pill">Online</span></div>
            <label>LLM provider</label><select value={provider} onChange={e => setProvider(e.target.value)}><option value="openai">OpenAI</option><option value="gemini">Gemini</option><option value="ollama">Ollama (Local)</option></select>
            <div className="messages">{messages.map((m, i) => <div key={i} className={`msg ${m.role}`}><span>{m.role === 'assistant' ? 'AI' : 'You'}</span><div>{m.content}</div></div>)}{busy && <p className="muted">Understanding requirements and searching…</p>}</div>
            <form className="composer" onSubmit={send}><input value={input} onChange={e => setInput(e.target.value)} placeholder="Search for your dream plot here" /><button disabled={busy || !input.trim()}>Send</button></form><small className="muted">Demo only. Do not enter sensitive personal information.</small></section>
            <section className="results panel"><div className="heading"><div><h2>Matching properties</h2><p>Retrieved from connected property data</p></div><span className="pill">{properties.length} results</span></div>
                {!properties.length ? <div className="empty"><div>⌂</div><h3>Your property results will appear here</h3><p>Ask the assistant for a location, budget or BHK requirement.</p></div> : <div className="cards">{properties.map((p, i) => <article key={p.property_id || i}>{p.image_url ? <img src={p.image_url} alt="Property" /> : <div className="placeholder">Image unavailable</div>}<div className="info"><b>{p.property_type || 'Property'} {p.bhk ? `· ${p.bhk} BHK` : ''}</b><p>{[p.location, p.city].filter(Boolean).join(', ')}</p><strong>{p.price ? `₹${Number(p.price).toLocaleString('en-IN')}` : 'Price on request'}</strong><small>ID: {p.property_id || 'Not provided'}</small><button className="secondary" onClick={() => { setSelected(p); setNotice('') }}>Contact about property</button></div></article>)}</div>}
                {selected && <div className="overlay"><form className="modal" onSubmit={submit}><button type="button" className="close" onClick={() => setSelected(null)}>×</button><h3>Contact our property team</h3><p>Property: {selected.property_id || 'Selected property'}</p><input required placeholder="Your name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} /><input required placeholder="Phone number" value={form.phone} onChange={e => setForm({ ...form, phone: e.target.value })} /><textarea required value={form.message} onChange={e => setForm({ ...form, message: e.target.value })} /><label className="consent"><input type="checkbox" checked={form.consent} onChange={e => setForm({ ...form, consent: e.target.checked })} /> I agree to be contacted about this enquiry.</label><button disabled={!form.consent}>Submit enquiry</button></form></div>}
                {notice && <p className="notice">{notice}</p>}</section></main><footer>Demo experience · Property availability must be confirmed by the property team.</footer></div>
}
