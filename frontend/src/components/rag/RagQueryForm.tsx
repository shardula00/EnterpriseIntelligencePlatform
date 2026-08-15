import { useState } from 'react'

export function RagQueryForm({
  onAsk,
  disabled,
}: {
  onAsk: (question: string) => void
  disabled?: boolean
}) {
  const [question, setQuestion] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = question.trim()
    if (!trimmed) return
    onAsk(trimmed)
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      aria-label="Ask your enterprise documents"
    >
      <h2 className="text-sm font-semibold text-slate-900">🤖 Ask your enterprise documents</h2>
      <div className="mt-3 flex flex-col gap-3 sm:flex-row">
        <label htmlFor="rag-question" className="sr-only">
          Question
        </label>
        <input
          id="rag-question"
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="What is the company's data retention policy?"
          disabled={disabled}
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm placeholder:text-slate-400 focus:border-accent-500 focus:outline-none disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={disabled || !question.trim()}
          className="rounded-md bg-accent-600 px-5 py-2 text-sm font-medium text-white hover:bg-accent-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {disabled ? 'Asking…' : 'Ask'}
        </button>
      </div>
    </form>
  )
}
