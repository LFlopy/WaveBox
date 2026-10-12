import { useMemo, useState } from "react";
import TrackList from "../components/TrackList.jsx";
import { ListSkeleton, ErrorBox, EmptyState } from "../components/Status.jsx";
import { SearchIcon } from "../components/icons.jsx";

export default function SearchView({ tracks, loading, error, onRetry, listProps }) {
  const [query, setQuery] = useState("");

  // Пока ищем по уже загруженным трекам. С бэкендом здесь будет fetch(`/api/search?q=...`)
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return tracks.filter(
      (t) => t.title.toLowerCase().includes(q) || t.artist.toLowerCase().includes(q)
    );
  }, [query, tracks]);

  const hasQuery = query.trim().length > 0;

  return (
    <>
      <div className="relative mb-6">
        <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-mist/60" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search tracks or artists"
          aria-label="Search"
          className="h-12 w-full rounded-2xl border border-violet/40 bg-ink pl-12 pr-4 text-mist outline-none transition placeholder:text-mist/40 focus:border-violet focus:ring-2 focus:ring-violet/50"
        />
      </div>

      {loading && <ListSkeleton rows={4} />}
      {error && <ErrorBox message={error} onRetry={onRetry} />}
      {!loading && !error && !hasQuery && <EmptyState>Type something to find a track.</EmptyState>}
      {!loading && !error && hasQuery && results.length === 0 && (
        <EmptyState>Nothing found for “{query.trim()}”.</EmptyState>
      )}
      {!loading && !error && results.length > 0 && <TrackList tracks={results} {...listProps} />}
    </>
  );
}
