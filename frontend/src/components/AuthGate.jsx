import { useState, useEffect } from 'react'
import { API_BASE, IS_CLOUD } from '../config'

const TOKEN_KEY = 'hl_token'
const TOKEN_TS_KEY = 'hl_token_ts'
const SESSION_MAX_MS = 24 * 60 * 60 * 1000 // 24 hours

function isSessionValid() {
  const token = sessionStorage.getItem(TOKEN_KEY)
  const ts = sessionStorage.getItem(TOKEN_TS_KEY)
  if (!token || !ts) return false
  const elapsed = Date.now() - parseInt(ts, 10)
  return elapsed < SESSION_MAX_MS
}

export function clearAuthSession() {
  sessionStorage.removeItem(TOKEN_KEY)
  sessionStorage.removeItem(TOKEN_TS_KEY)
}

export default function AuthGate({ children }) {
  const [authed, setAuthed] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  // If not cloud mode, render children directly
  if (!IS_CLOUD) return children

  useEffect(() => {
    if (isSessionValid()) {
      setAuthed(true)
    }
  }, [])

  if (authed) return children

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/status`, {
        headers: { Authorization: `Bearer ${password}` },
      })
      if (res.ok) {
        sessionStorage.setItem(TOKEN_KEY, password)
        sessionStorage.setItem(TOKEN_TS_KEY, String(Date.now()))
        setAuthed(true)
      } else {
        setError('Invalid password')
      }
    } catch {
      setError('Connection failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <form
        onSubmit={handleSubmit}
        className="bg-gray-900 border border-gray-800 rounded-xl p-8 w-full max-w-sm shadow-lg"
      >
        <h1 className="text-2xl font-bold text-white mb-6 text-center">
          Halcyon Lab
        </h1>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Dashboard password"
          className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4"
          autoFocus
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !password}
          className="w-full py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors"
        >
          {loading ? 'Signing in...' : 'Sign in'}
        </button>
        {error && (
          <p className="mt-3 text-red-400 text-sm text-center">{error}</p>
        )}
      </form>
    </div>
  )
}
