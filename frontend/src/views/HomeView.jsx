import TrackList from "../components/TrackList.jsx";
import { ListSkeleton, ErrorBox, EmptyState } from "../components/Status.jsx";

export default function HomeView({ tracks, loading, error, onRetry, listProps }) {
  return (
    <>
      <h2 className="mb-4 text-2xl font-semibold text-mist">
        Home
        {!loading && !error && <span className="ml-3 text-base font-normal text-mist/50">{tracks.length} tracks</span>}
      </h2>

      {loading && <ListSkeleton />}
      {error && <ErrorBox message={error} onRetry={onRetry} />}
      {!loading && !error && tracks.length === 0 && <EmptyState>Your library is empty. Find tracks in Search and add them to a playlist.</EmptyState>}
      {!loading && !error && tracks.length > 0 && <TrackList tracks={tracks} {...listProps} />}
    </>
  );
}
