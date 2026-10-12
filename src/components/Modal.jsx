import { useEffect, useId, useRef } from "react";
import { CloseIcon } from "./icons.jsx";

// Обёртка над встроенным <dialog>: сам закрывается по Esc, держит фокус внутри,
// затемняет фон. Закрывается и по клику на затемнение.
export default function Modal({ title, onClose, children }) {
  const ref = useRef(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (dialog && !dialog.open) dialog.showModal();
  }, []);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose(); // клик мимо окна
      }}
      className="m-auto w-[calc(100%-2rem)] max-w-md rounded-3xl border border-violet/40 bg-card p-0 text-mist shadow-[0_0_40px_rgba(139,95,191,0.4)] backdrop:bg-black/60 backdrop:backdrop-blur-sm"
    >
      <div className="flex max-h-[80dvh] flex-col p-5">
        <div className="mb-4 flex items-start justify-between gap-3">
          <h2 id={titleId} className="text-lg font-semibold">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="-mr-1 -mt-1 rounded-full p-2 text-mist/60 transition hover:bg-mist/10 hover:text-mist"
          >
            <CloseIcon className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </dialog>
  );
}
