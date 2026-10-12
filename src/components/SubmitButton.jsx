// Кнопка-«таблетка» с круглой стрелкой справа и состоянием загрузки.
export default function SubmitButton({ children, loading }) {
  return (
    <button
      type="submit"
      disabled={loading}
      className="relative flex h-10 w-full items-center justify-center rounded-full bg-violet text-sm font-medium text-mist
        shadow-[0_0_16px_rgba(139,95,191,0.45)] transition hover:brightness-110
        focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mist
        disabled:cursor-not-allowed disabled:opacity-70"
    >
      {loading ? "Please wait…" : children}

      <span className="absolute right-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-white">
        {loading ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-violet border-t-transparent" />
        ) : (
          <svg viewBox="0 0 24 24" className="h-4 w-4 text-violet" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M5 12h14M13 6l6 6-6 6" />
          </svg>
        )}
      </span>
    </button>
  );
}
