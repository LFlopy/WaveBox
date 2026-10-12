import { useEffect, useRef, useState } from "react";
import Cover from "./Cover.jsx";
import { PlayIcon, PauseIcon, PrevIcon, NextIcon } from "./icons.jsx";

const toSeconds = (str) => {
  const [m, s] = str.split(":").map(Number);
  return m * 60 + s;
};
const format = (sec) =>
  `${Math.floor(sec / 60)}:${String(Math.floor(sec % 60)).padStart(2, "0")}`;

export default function Player({ track, isPlaying, canSkip, onTogglePlay, onPrev, onNext, onEnded }) {
  const audioRef = useRef(null);

  // Прогресс и длительность привязаны к id трека, поэтому при смене трека
  // они сбрасываются сразу, без «хвостов» от прошлой песни.
  const [progress, setProgress] = useState({ id: null, time: 0 });
  const [meta, setMeta] = useState({ id: null, duration: 0 });
  const [failedId, setFailedId] = useState(null);

  const current = track && progress.id === track.id ? progress.time : 0;
  const audioDuration = track && meta.id === track.id ? meta.duration : 0;
  // Если аудио загрузилось, берём настоящую длительность файла
  const total = audioDuration || (track ? toSeconds(track.duration) : 0);

  const setCurrent = (updater) => {
    if (!track) return;
    setProgress((prev) => {
      const base = prev.id === track.id ? prev.time : 0;
      return { id: track.id, time: typeof updater === "function" ? updater(base) : updater };
    });
  };

  // Если у трека есть audioUrl, управляем настоящим <audio>
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || !track?.audioUrl) return;
    if (isPlaying) audio.play().catch(() => {});
    else audio.pause();
  }, [isPlaying, track]);

  // Если audioUrl пустой, имитируем воспроизведение таймером
  useEffect(() => {
    if (!isPlaying || !track || track.audioUrl) return;
    const id = setInterval(() => setCurrent((c) => Math.min(c + 0.25, total)), 250);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaying, track, total]);

  // Имитация дошла до конца
  useEffect(() => {
    if (track && !track.audioUrl && isPlaying && total > 0 && current >= total) onEnded();
  }, [current, isPlaying, total, track, onEnded]);

  const seek = (value) => {
    setCurrent(value);
    if (audioRef.current) audioRef.current.currentTime = value;
  };

  const handleToggle = () => {
    if (total > 0 && current >= total) seek(0); // после конца начинаем заново
    onTogglePlay();
  };

  // Как в большинстве плееров: если играет больше 3 секунд, «назад» перематывает на начало
  const handlePrev = () => {
    if (current > 3 || !canSkip) seek(0);
    else onPrev();
  };

  const skipButton =
    "flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-mist transition hover:bg-mist/10 focus-visible:outline-2 focus-visible:outline-violet disabled:opacity-30 disabled:hover:bg-transparent";

  return (
    <section
      aria-label="Player"
      className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-3 rounded-3xl bg-ink/85 px-4 py-3 backdrop-blur-md md:flex md:h-28 md:gap-6 md:px-8 md:py-4"
    >
      {track?.audioUrl && (
        <audio
          ref={audioRef}
          src={track.audioUrl}
          onTimeUpdate={(e) => setCurrent(e.currentTarget.currentTime)}
          onLoadedMetadata={(e) => {
            const d = e.currentTarget.duration;
            if (Number.isFinite(d)) setMeta({ id: track.id, duration: d });
          }}
          onEnded={onEnded}
          onError={() => {
            setFailedId(track.id);
            if (isPlaying) onTogglePlay();
          }}
        />
      )}

      {/* Что играет */}
      <div className="flex min-w-0 items-center gap-3 md:w-1/4">
        {track ? (
          <>
            <Cover id={track.id} src={track.cover} alt="" className="h-14 w-14 shrink-0 rounded-xl" />
            <div className="min-w-0">
              <p className="truncate font-medium text-mist">{track.title}</p>
              <p className="truncate text-sm text-mist/60">{track.artist}</p>
              {failedId === track.id && (
                <p className="text-xs text-red-300">Can't load audio. Check audioUrl</p>
              )}
            </div>
          </>
        ) : (
          <p className="text-sm text-mist/60">Select a track to play</p>
        )}
      </div>

      {/* Кнопки */}
      <div className="flex items-center gap-1">
        <button type="button" onClick={handlePrev} disabled={!track} aria-label="Previous track" className={skipButton}>
          <PrevIcon className="h-5 w-5" />
        </button>
        <button
          type="button"
          onClick={handleToggle}
          disabled={!track}
          aria-label={isPlaying ? "Pause" : "Play"}
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-mist text-violet transition hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mist disabled:opacity-40"
        >
          {isPlaying ? <PauseIcon className="h-5 w-5" /> : <PlayIcon className="h-5 w-5" />}
        </button>
        <button type="button" onClick={onNext} disabled={!track || !canSkip} aria-label="Next track" className={skipButton}>
          <NextIcon className="h-5 w-5" />
        </button>
      </div>

      {/* Прогресс */}
      <div className="col-span-2 flex flex-1 items-center gap-3 md:col-span-1">
        <span className="w-10 text-right text-xs tabular-nums text-mist/70">{format(current)}</span>
        <input
          type="range"
          min={0}
          max={total || 1}
          step={1}
          value={Math.floor(current)}
          onChange={(e) => seek(Number(e.target.value))}
          disabled={!track}
          aria-label="Track progress"
          className="h-1.5 flex-1 cursor-pointer accent-violet disabled:cursor-default disabled:opacity-40"
        />
        <span className="w-10 text-xs tabular-nums text-mist/70">{format(total)}</span>
      </div>
    </section>
  );
}
