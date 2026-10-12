import { useState } from "react";
import Modal from "./Modal.jsx";
import Cover from "./Cover.jsx";
import { HeartFilledIcon, CheckIcon, PlusIcon } from "./icons.jsx";

// «Добавить в плейлист»: клик по плейлисту добавляет трек (повторный клик убирает).
// Внизу можно сразу создать новый плейлист, трек попадёт в него автоматически.
export default function PlaylistPickerModal({ track, playlists, onToggle, onCreate, onClose }) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

  const handleCreate = (e) => {
    e.preventDefault();
    const trimmed = name.trim();
    if (!trimmed) return;
    onCreate(trimmed, track.id);
    setName("");
    setCreating(false);
  };

  return (
    <Modal title="Add to playlist" onClose={onClose}>
      <p className="-mt-2 mb-4 truncate text-sm text-mist/60">
        {track.title} · {track.artist}
      </p>

      <ul className="scrollbar-dark -mr-2 min-h-0 flex-1 space-y-1 overflow-y-auto pr-2">
        {playlists.map((p) => {
          const has = p.trackIds.includes(track.id);
          return (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => onToggle(p.id, track.id)}
                aria-pressed={has}
                className={`flex w-full items-center gap-3 rounded-2xl px-2 py-2 text-left transition hover:bg-mist/5 focus-visible:outline-2 focus-visible:outline-violet ${
                  has ? "bg-violet/20" : ""
                }`}
              >
                <Cover
                  id={p.id}
                  src={p.cover}
                  icon={p.system ? HeartFilledIcon : undefined}
                  className="h-10 w-10 shrink-0 rounded-lg"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{p.name}</span>
                  <span className="block text-xs text-mist/60">{p.trackIds.length} tracks</span>
                </span>
                {has && <CheckIcon className="h-5 w-5 shrink-0 text-lilac" />}
              </button>
            </li>
          );
        })}
      </ul>

      <div className="mt-4 border-t border-violet/20 pt-4">
        {creating ? (
          <form onSubmit={handleCreate} className="flex gap-2">
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={40}
              placeholder="Playlist name"
              aria-label="New playlist name"
              className="h-10 min-w-0 flex-1 rounded-xl border border-violet/40 bg-ink px-3 text-sm text-mist outline-none placeholder:text-mist/40 focus:border-violet focus:ring-2 focus:ring-violet/50"
            />
            <button type="submit" disabled={!name.trim()} className="rounded-full bg-violet px-4 text-sm text-mist transition hover:brightness-110 disabled:opacity-50">
              Create
            </button>
            <button type="button" onClick={() => { setCreating(false); setName(""); }} className="px-2 text-sm text-mist/70 transition hover:text-mist">
              Cancel
            </button>
          </form>
        ) : (
          <div className="flex items-center justify-between gap-3">
            <button
              type="button"
              onClick={() => setCreating(true)}
              className="flex items-center gap-2 rounded-full border border-violet/50 px-4 py-2 text-sm text-mist transition hover:bg-violet/20"
            >
              <PlusIcon className="h-4 w-4" /> Create playlist
            </button>
            <button type="button" onClick={onClose} className="rounded-full bg-violet px-5 py-2 text-sm text-mist transition hover:brightness-110">
              Done
            </button>
          </div>
        )}
      </div>
    </Modal>
  );
}
