import { useId, useState } from "react";
import { EyeIcon, EyeOffIcon } from "./icons.jsx";

// Поле ввода с подписью и ошибкой. Для type="password" добавляется глазик.
export default function TextField({ label, error, type = "text", ...inputProps }) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const isPassword = type === "password";

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="pl-1 text-xs text-mist">
        {label}
      </label>

      <div className="relative">
        <input
          id={id}
          type={isPassword && visible ? "text" : type}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          className={`h-10 w-full rounded-xl border bg-ink px-3 text-sm text-mist outline-none transition
            focus:border-violet focus:ring-2 focus:ring-violet/50
            ${isPassword ? "pr-10" : ""}
            ${error ? "border-red-400/70" : "border-violet/40"}`}
          {...inputProps}
        />

        {isPassword && (
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            onMouseDown={(e) => e.preventDefault()} // чтобы поле не теряло фокус
            aria-label={visible ? "Hide password" : "Show password"}
            aria-pressed={visible}
            className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-xl text-mist/60 transition hover:text-mist focus-visible:text-mist focus-visible:outline-none"
          >
            {visible ? <EyeOffIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
          </button>
        )}
      </div>

      {error && (
        <p id={`${id}-error`} className="pl-1 text-xs text-red-300">
          {error}
        </p>
      )}
    </div>
  );
}
