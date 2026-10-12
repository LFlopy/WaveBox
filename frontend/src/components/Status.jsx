// Состояния «загрузка» и «ошибка», общие для всех вкладок.
export function ListSkeleton({ rows = 6 }) {
  return (
    <ul className="flex flex-col gap-2" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <li key={i} className="flex animate-pulse items-center gap-4 px-3 py-2">
          <div className="h-12 w-12 rounded-xl bg-mist/10" />
          <div className="flex-1 space-y-2">
            <div className="h-3 w-1/3 rounded bg-mist/10" />
            <div className="h-3 w-1/5 rounded bg-mist/10" />
          </div>
          <div className="h-3 w-8 rounded bg-mist/10" />
        </li>
      ))}
    </ul>
  );
}

export function ErrorBox({ message, onRetry }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-red-400/40 bg-red-400/10 p-4 text-sm text-red-200">
      <p>{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-full bg-violet px-4 py-1.5 text-mist transition hover:brightness-110"
      >
        Try again
      </button>
    </div>
  );
}

export function EmptyState({ children }) {
  return <p className="py-10 text-center text-sm text-mist/60">{children}</p>;
}
