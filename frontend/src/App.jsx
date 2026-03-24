import { useEffect, useRef } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query'
import Layout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import ToastContainer, { toast } from './components/Toast'
import Dashboard from './pages/Dashboard'
import Packets from './pages/Packets'
import ShadowLedger from './pages/ShadowLedger'
import Training from './pages/Training'
import Review from './pages/Review'
import CTOReport from './pages/CTOReport'
import Settings from './pages/Settings'
import Roadmap from './pages/Roadmap'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchInterval: 30000, staleTime: 10000 },
  },
})

function WebSocketProvider({ children }) {
  const qc = useQueryClient()
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  useEffect(() => {
    function connect() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/live`)
      wsRef.current = ws

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          const type = msg.type
          // Invalidate relevant caches based on event type
          if (type === 'scan_complete') {
            qc.invalidateQueries({ queryKey: ['scan'] })
            qc.invalidateQueries({ queryKey: ['status'] })
            toast('Scan complete', 'info')
          } else if (type === 'trade_opened') {
            qc.invalidateQueries({ queryKey: ['shadow'] })
            toast(`Trade opened: ${msg.data?.ticker || ''}`, 'info')
          } else if (type === 'trade_closed') {
            qc.invalidateQueries({ queryKey: ['shadow'] })
            const pnl = msg.data?.pnl_dollars
            const type = pnl >= 0 ? 'success' : 'error'
            toast(`Trade closed: ${msg.data?.ticker || ''} $${pnl?.toFixed(2) || ''}`, type)
          } else if (type === 'pnl_update') {
            qc.invalidateQueries({ queryKey: ['shadow'] })
          } else if (type === 'training_update') {
            qc.invalidateQueries({ queryKey: ['training'] })
            toast('Training update', 'info')
          } else if (type === 'system_status') {
            qc.invalidateQueries({ queryKey: ['status'] })
          }
        } catch (e) { /* ignore parse errors */ }
      }

      ws.onclose = () => {
        reconnectRef.current = setTimeout(connect, 5000)
      }

      ws.onerror = () => {
        ws.close()
      }
    }

    connect()
    return () => {
      if (wsRef.current) wsRef.current.close()
      if (reconnectRef.current) clearTimeout(reconnectRef.current)
    }
  }, [qc])

  return children
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <WebSocketProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<Dashboard />} />
                <Route path="/packets" element={<Packets />} />
                <Route path="/shadow" element={<ShadowLedger />} />
                <Route path="/training" element={<Training />} />
                <Route path="/review" element={<Review />} />
                <Route path="/cto-report" element={<CTOReport />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/roadmap" element={<Roadmap />} />
              </Route>
            </Routes>
          </BrowserRouter>
          <ToastContainer />
        </WebSocketProvider>
      </ErrorBoundary>
    </QueryClientProvider>
  )
}
