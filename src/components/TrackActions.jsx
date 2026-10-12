import { HeartIcon, PlusIcon, TrashIcon } from "./icons.jsx";
import { LIKED_NAME } from "../api/musicApi.js";

const base =
  "flex h-9 w-9 shrink-0 items-center justify-center rounded-full transition hover:bg-mist/10 focus-visible:outline-2 focus-visible:outline-violet";

// Кнопки в строке трека: лайк, добавить в плейлист, убрать из плейлиста.
// Показывается только то, для чего передан обработчик.
export default function TrackActions({ liked, onLike, onAdd, onRemove }) {
  return (
    <div className="flex items-center">
      {onLike && (
        <button
          type="button"
          onClick={onLike}
          aria-pressed={liked}
          aria-label={liked ? `Remove from ${LIKED_NAME}` : `Add to ${LIKED_NAME}`}
          className={`${base} ${liked ? "text-lilac" : "text-mist/60 hover:text-mist"}`}
        >
          <HeartIcon filled={liked} className="h-5 w-5" />
        </button>
      )}
      {onAdd && (
        <button type="button" onClick={onAdd} aria-label="Add to playlist" className={`${base} text-mist/60 hover:text-mist`}>
          <PlusIcon className="h-5 w-5" />
        </button>
      )}
      {onRemove && (
        <button type="button" onClick={onRemove} aria-label="Remove from playlist" className={`${base} text-mist/60 hover:text-red-300`}>
          <TrashIcon className="h-5 w-5" />
        </button>
      )}
    </div>
  );
}
