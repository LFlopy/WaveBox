import Cover from "./Cover.jsx";

function Equalizer({ playing }) {
  const heights = ["60%", "100%", "40%"];
  return (
    <span className="flex h-4 items-end gap-0.5" aria-hidden="true">
      {heights.map((h, i) => (
        <span
          key={i}
          className={`w-1 rounded-sm bg-lilac ${playing ? "animate-pulse" : ""}`}
          style={{ height: h, animationDelay: `${i * 150}ms` }}
        />
      ))}
    </span>
  );
}

// Список треков. Клик по строке вызывает onSelect(track, tracks).
// renderActions(track) рисует кнопки справа (лайк, «+», удалить).
export default function TrackList({ tracks, currentId, isPlaying, onSelect, renderActions }) {
  return (
    <ul className="flex flex-col gap-1">
      {tracks.map((track) => {
        const active = track.id === currentId;
        return (
          <li
            key={track.id}
            className={`flex items-center gap-1 rounded-2xl pr-2 transition ${
              active ? "bg-violet/25" : "hover:bg-mist/5"
            }`}
          >
            <button
              type="button"
              onClick={() => onSelect(track, tracks)}
              aria-current={active ? "true" : undefined}
              className="flex min-w-0 flex-1 items-center gap-4 rounded-2xl px-3 py-2 text-left focus-visible:outline-2 focus-visible:outline-violet"
            >
              <Cover id={track.id} src={track.cover} alt="" className="h-12 w-12 shrink-0 rounded-xl" />

              <span className="min-w-0 flex-1">
                <span className={`block truncate font-medium ${active ? "text-lilac" : "text-mist"}`}>
                  {track.title}
                </span>
                <span className="block truncate text-sm text-mist/60">{track.artist}</span>
              </span>

              {active && <Equalizer playing={isPlaying} />}
              <span className="text-sm tabular-nums text-mist/60">{track.duration}</span>
            </button>

            {renderActions?.(track)}
          </li>
        );
      })}
    </ul>
  );
}
