import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { CheckCircle2, CircleX, Info, AlertTriangle } from 'lucide-react'

type ToastKind = 'success' | 'error' | 'info' | 'warning'

interface Toast {
  id: number
  kind: ToastKind
  text: string
}

const listeners = new Set<(toast: Toast) => void>()
let nextId = 0

export function toast(text: string, kind: ToastKind = 'info') {
  listeners.forEach((fn) => fn({ id: ++nextId, kind, text }))
}

const ICONS: Record<ToastKind, ReactNode> = {
  success: <CheckCircle2 className="size-4 shrink-0 text-green-600" />,
  error: <CircleX className="size-4 shrink-0 text-red-600" />,
  info: <Info className="size-4 shrink-0 text-blue-600" />,
  warning: <AlertTriangle className="size-4 shrink-0 text-amber-600" />,
}

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([])

  useEffect(() => {
    const add = (t: Toast) =>
      setToasts((prev) => {
        const next = [...prev, t]
        setTimeout(() => {
          setToasts((cur) => cur.filter((x) => x.id !== t.id))
        }, 5000)
        return next
      })
    listeners.add(add)
    return () => {
      listeners.delete(add)
    }
  }, [])

  return (
    <div className="fixed right-4 bottom-4 z-[100] flex w-80 flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className="bg-card text-card-foreground flex items-start gap-2 rounded-lg border p-3 text-sm shadow-lg"
        >
          {ICONS[t.kind]}
          <span className="min-w-0 break-words">{t.text}</span>
        </div>
      ))}
    </div>
  )
}