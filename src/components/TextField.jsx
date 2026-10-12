import { useId } from "react";

// Поле ввода с подписью и текстом ошибки.
export default function TextField({ label, error, ...inputProps }) {
  const id = useId();

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="pl-1 text-xs text-mist">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`h-10 w-full rounded-xl border bg-ink px-3 text-sm text-mist outline-none transition
          focus:border-violet focus:ring-2 focus:ring-violet/50
          ${error ? "border-red-400/70" : "border-violet/40"}`}
        {...inputProps}
      />
      {error && (
        <p id={`${id}-error`} className="pl-1 text-xs text-red-300">
          {error}
        </p>
      )}
    </div>
  );
}
