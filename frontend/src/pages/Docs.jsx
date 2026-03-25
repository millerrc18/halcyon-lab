import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
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
        html.push(`<pre class="bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-lg p-4 overflow-x-auto text-sm font-mono my-3">${codeLines.join('\n')}</pre>`)
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
      html.push(`<h${level} class="${cls} text-[var(--text-primary)]">${inline(text)}</h${level}>`)
      continue
    }

    if (line.match(/^[-*]\s/)) {
      if (!inList) { html.push('<ul class="list-disc list-inside space-y-1 my-2 text-sm text-[var(--text-secondary)]">'); inList = true }
      html.push(`<li>${inline(line.replace(/^[-*]\s*/, ''))}</li>`)
      continue
    }

    if (line.match(/^\d+\.\s/)) {
      if (!inList) { html.push('<ul class="list-decimal list-inside space-y-1 my-2 text-sm text-[var(--text-secondary)]">'); inList = true }
      html.push(`<li>${inline(line.replace(/^\d+\.\s*/, ''))}</li>`)
      continue
    }

    if (inList && line.trim() === '') { html.push('</ul>'); inList = false; continue }
    if (inList && !line.match(/^\s/)) { html.push('</ul>'); inList = false }

    if (line.match(/^---+$/)) {
      html.push('<hr class="border-[var(--border)] my-6" />')
      continue
    }

    if (line.trim() === '') {
      html.push('<div class="h-3"></div>')
      continue
    }

    html.push(`<p class="text-sm text-[var(--text-secondary)] leading-relaxed my-1">${inline(line)}</p>`)
  }

  if (inList) html.push('</ul>')
  if (inCode) html.push(`<pre class="bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-lg p-4 overflow-x-auto text-sm font-mono my-3">${codeLines.join('\n')}</pre>`)

  return html.join('\n')
}

function inline(text) {
  return text
    .replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-[var(--text-primary)] font-medium">$1</strong>')
    .replace(/`(.+?)`/g, '<code class="bg-[var(--bg-tertiary)] px-1.5 py-0.5 rounded text-xs font-mono">$1</code>')
    .replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2" class="text-blue-400 hover:underline" target="_blank" rel="noopener">$1</a>')
}

export default function Docs() {
  const [activeDoc, setActiveDoc] = useState('agents')
  const { data: docList } = useQuery({
    queryKey: ['docs-list'],
    queryFn: () => fetch('/api/docs').then(r => r.json()),
  })
  const { data: doc, isLoading } = useQuery({
    queryKey: ['doc', activeDoc],
    queryFn: () => fetch(`/api/docs/${activeDoc}`).then(r => r.json()),
    enabled: !!activeDoc,
  })

  return (
    <div className="flex gap-6 max-w-5xl mx-auto">
      <nav className="w-48 shrink-0">
        <h2 className="text-sm font-medium text-[var(--text-muted)] uppercase tracking-wide mb-3">Documentation</h2>
        <div className="space-y-1">
          {(docList || []).map(d => (
            <button
              key={d.id}
              onClick={() => setActiveDoc(d.id)}
              disabled={!d.available}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${
                activeDoc === d.id
                  ? 'bg-[var(--bg-tertiary)] text-[var(--text-primary)]'
                  : d.available
                    ? 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]/50'
                    : 'text-[var(--text-muted)] opacity-50 cursor-not-allowed'
              }`}
            >
              {d.title}
            </button>
          ))}
        </div>
      </nav>

      <div className="flex-1 min-w-0">
        {isLoading ? (
          <LoadingSpinner />
        ) : doc ? (
          <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-lg p-6">
            <div
              dangerouslySetInnerHTML={{ __html: renderMarkdown(doc.content) }}
            />
          </div>
        ) : (
          <div className="text-center text-[var(--text-muted)] py-12">Select a document</div>
        )}
      </div>
    </div>
  )
}
