import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-baseline gap-2">
            <span className="text-lg font-semibold text-slate-900">Enterprise Intelligence</span>
            <span className="text-xs font-medium text-slate-400">Platform</span>
          </Link>
          <nav className="text-sm text-slate-500">
            <Link to="/" className="hover:text-accent-600">
              Datasets
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
    </div>
  )
}
