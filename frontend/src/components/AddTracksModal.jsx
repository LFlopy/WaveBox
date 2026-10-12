import { useMemo, useState } from "react";
import Modal from "./Modal.jsx";
import Cover from "./Cover.jsx";
import { CheckIcon, SearchIcon } from "./icons.jsx";

// «Добавить треки в этот плейлист»: список всего каталога с поиском.
export default function AddTracksModal({ tracks, playlist, onToggle, onClose }) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tracks;
    return tracks.filter((t) => t.title.toLowerCase().includes(q) || t.artist.toLowerCase().includes(q));
  }, [query, tracks]);

  return (
    <Modal title={`Add tracks to “${playlist.name}”`} onClose={onClose}>
      <div className="relative mb-3">
        <SearchIcon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-mist/60" />
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search tracks or artists"
          aria-label="Search tracks"
          className="h-10 w-full rounded-xl border border-violet/40 bg-ink pl-9 pr-3 text-sm text-mist outline-none placeholder:text-mist/40 focus:border-violet focus:ring-2 focus:ring-violet/50"
        />
      </div>

      {filtered.length === 0 ? (
        <p className="py-8 text-center text-sm text-mist/60">
          {tracks.length === 0 ? "The catalog is empty." : "Nothing found."}
        </p>
      ) : (
        <ul className="scrollbar-dark -mr-2 min-h-0 flex-1 space-y-1 overflow-y-auto pr-2">
          {filtered.map((t) => {
            const has = playlist.trackIds.includes(t.id);
            return (
              <li key={t.id}>
                <button
                  type="button"
                  onClick={() => onToggle(t.id)}
                  aria-pressed={has}
                  className={`flex w-full items-center gap-3 rounded-2xl px-2 py-2 text-left transition hover:bg-mist/5 focus-visible:outline-2 focus-visible:outline-violet ${
                    has ? "bg-violet/20" : ""
                  }`}
                >
                  <Cover id={t.id} src={t.cover} className="h-10 w-10 shrink-0 rounded-lg" />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{t.title}</span>
                    <span className="block truncate text-xs text-mist/60">{t.artist}</span>
                  </span>
                  {has && <CheckIcon className="h-5 w-5 shrink-0 text-lilac" />}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div className="mt-4 flex justify-end border-t border-violet/20 pt-4">
        <button type="button" onClick={onClose} className="rounded-full bg-violet px-5 py-2 text-sm text-mist transition hover:brightness-110">
          Done
        </button>
      </div>
    </Modal>
  );
}
