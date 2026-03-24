import { useState, useEffect, useCallback } from 'react'

let addToastGlobal = null

export function useToast() {
  return { addToast: addToastGlobal }
}

export function toast(message, type = 'info') {
  if (addToastGlobal) addToastGlobal({ message, type })
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback(({ message, type = 'info' }) => {
    const id = Date.now() + Math.random()
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 5000)
  }, [])

  useEffect(() => {
    addToastGlobal = addToast
    return () => { addToastGlobal = null }
  }, [addToast])

  const colors = {
    success: 'bg-green-900/90 border-green-700 text-green-200',
    error: 'bg-red-900/90 border-red-700 text-red-200',
    info: 'bg-blue-900/90 border-blue-700 text-blue-200',
    warning: 'bg-yellow-900/90 border-yellow-700 text-yellow-200',
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map(t => (
        <div key={t.id}
          className={`px-4 py-3 rounded border text-sm shadow-lg ${colors[t.type] || colors.info}`}
        >
          {t.message}
        </div>
      ))}
    </div>
  )
}
