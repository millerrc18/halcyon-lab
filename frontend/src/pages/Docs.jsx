import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import LoadingSpinner from '../components/LoadingSpinner'

function renderMarkdown(md) {
  if (!md) return ''
  const lines = md.split('\n')
  const html = []
  let inCode = false
  let codeLines = []
  let inList = false

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    if (line.startsWith('```')) {
      if (inCode) {
        html.push(`<pre style="background:var(--slate-800);border:1px solid var(--slate-600);border-radius:var(--radius-lg);padding:1rem;overflow-x:auto;font-size:0.875rem;font-family:var(--font-mono);margin:0.75rem 0">${codeLines.join('\n')}</pre>`)
        codeLines = []
        inCode = false
      } else {
        if (inList) { html.push('</ul>'); inList = false }
        inCode = true
      }
      continue
    }

    if (inCode) {
      codeLines.push(line.replace(/</g, '&lt;').replace(/>/g, '&gt;'))
      continue
    }

    if (line.match(/^#{1,6}\s/)) {
      if (inList) { html.push('</ul>'); inList = false }
      const level = line.match(/^(#+)/)[1].length
      const text = line.replace(/^#+\s*/, '')
      const sizes = { 1: 'text-xl font-medium mt-8 mb-3', 2: 'text-lg font-medium mt-6 mb-2', 3: 'text-base font-medium mt-4 mb-2' }
      const cls = sizes[level] || 'text-sm font-medium mt-3 mb-1'
      html.push(`<h${level} class="${cls}" style="color:var(--slate-100)">${inline(text)}</h${level}>`)
      continue
    }

    if (line.match(/^[-*]\s/)) {
      if (!inList) { html.push('<ul class="list-disc list-inside space-y-1 my-2 text-sm" style="color:var(--slate-300)">'); inList = true }
      html.push(`<li>${inline(line.replace(/^[-*]\s*/, ''))}</li>`)
      continue
    }

    if (line.match(/^\d+\.\s/)) {
      if (!inList) { html.push('<ul class="list-decimal list-inside space-y-1 my-2 text-sm" style="color:var(--slate-300)">'); inList = true }
      html.push(`<li>${inline(line.replace(/^\d+\.\s*/, ''))}</li>`)
      continue
    }

    if (inList && line.trim() === '') { html.push('</ul>'); inList = false; continue }
    if (inList && !line.match(/^\s/)) { html.push('</ul>'); inList = false }

    if (line.match(/^---+$/)) {
      html.push(`<hr style="border-color:var(--slate-600);margin:1.5rem 0" />`)
      continue
    }

    if (line.trim() === '') {
      html.push('<div class="h-3"></div>')
      continue
    }

    html.push(`<p class="text-sm leading-relaxed my-1" style="color:var(--slate-300)">${inline(line)}</p>`)
  }

  if (inList) html.push('</ul>')
  if (inCode) html.push(`<pre style="background:var(--slate-800);border:1px solid var(--slate-600);border-radius:var(--radius-lg);padding:1rem;overflow-x:auto;font-size:0.875rem;font-family:var(--font-mono);margin:0.75rem 0">${codeLines.join('\n')}</pre>`)

  return html.join('\n')
}

function inline(text) {
  return text
    .replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong style="color:var(--slate-100);font-weight:500">$1</strong>')
    .replace(/`(.+?)`/g, '<code style="background:var(--slate-800);padding:0.125rem 0.375rem;border-radius:0.25rem;font-size:0.75rem;font-family:var(--font-mono)">$1</code>')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" style="color:var(--teal-400)" class="hover:underline" target="_blank" rel="noopener">$1</a>')
}

export default function Docs() {
  const [activeDoc, setActiveDoc] = useState('agents')
  const { data: docList } = useQuery({
    queryKey: ['docs-list'],
    queryFn: api.getDocsList,
  })
  const { data: doc, isLoading } = useQuery({
    queryKey: ['doc', activeDoc],
    queryFn: () => api.getDoc(activeDoc),
    enabled: !!activeDoc,
  })

  const groups = [
    { label: 'Core', ids: ['agents', 'readme', 'architecture', 'training-guide', 'roadmap'] },
    { label: 'Research \u2014 Training', ids: ['research-training-formats', 'research-quality-rubric', 'research-self-blinding', 'research-model-degradation', 'research-training-gaps', 'research-grpo', 'research-qwen-selection'] },
    { label: 'Research \u2014 Strategy', ids: ['research-alt-data', 'research-halcyon-framework', 'research-universe-size'] },
    { label: 'Research \u2014 Business', ids: ['research-fund-path', 'research-scaling-plan', 'research-options'] },
  ]

  const docMap = Object.fromEntries((docList || []).map(d => [d.id, d]))

  return (
    <div className="flex gap-6 max-w-5xl mx-auto">
      <nav className="w-56 shrink-0">
        <h2 className="text-sm font-medium uppercase tracking-wide mb-3" style={{ color: 'var(--slate-400)' }}>Documentation</h2>
        <div className="space-y-4">
          {groups.map(g => {
            const docs = g.ids.map(id => docMap[id]).filter(Boolean)
            if (docs.length === 0) return null
            return (
              <div key={g.label}>
                <div className="text-xs uppercase tracking-wide px-3 mb-1" style={{ color: 'var(--slate-400)' }}>{g.label}</div>
                <div className="space-y-0.5">
                  {docs.map(d => (
                    <button
                      key={d.id}
                      onClick={() => setActiveDoc(d.id)}
                      disabled={!d.available}
                      className="w-full text-left px-3 py-1.5 rounded-lg text-sm transition-colors"
                      style={{
                        background: activeDoc === d.id ? 'var(--slate-700)' : 'transparent',
                        color: activeDoc === d.id ? 'var(--slate-100)' : d.available ? 'var(--slate-300)' : 'var(--slate-500)',
                        opacity: !d.available ? 0.5 : 1,
                        cursor: !d.available ? 'not-allowed' : 'pointer',
                      }}
                    >
                      {d.title.replace('Research: ', '')}
                    </button>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      </nav>

      <div className="flex-1 min-w-0">
        {isLoading ? (
          <LoadingSpinner />
        ) : doc ? (
          <div className="rounded-lg p-6" style={{ background: 'var(--slate-700)', border: '1px solid var(--slate-600)' }}>
            <div
              dangerouslySetInnerHTML={{ __html: renderMarkdown(doc.content) }}
            />
          </div>
        ) : (
          <div className="text-center py-12" style={{ color: 'var(--slate-400)' }}>Select a document</div>
        )}
      </div>
    </div>
  )
}
