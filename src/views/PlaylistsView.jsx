import { useState } from "react";
import Cover from "../components/Cover.jsx";
import TrackList from "../components/TrackList.jsx";
import PlaylistForm from "../components/PlaylistForm.jsx";
import AddTracksModal from "../components/AddTracksModal.jsx";
import { ListSkeleton, ErrorBox, EmptyState } from "../components/Status.jsx";
import { PlusIcon, BackIcon, PencilIcon, HeartFilledIcon } from "../components/icons.jsx";

export default function PlaylistsView({
  playlists, tracks, loading, error, onRetry,
  onCreate, onUpdate, onToggleTrack, onRemoveTrack, listProps,
}) {
  const [selectedId, setSelectedId] = useState(null);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [addingTracks, setAddingTracks] = useState(false);

  const selected = playlists.find((p) => p.id === selectedId);

  if (loading) return <ListSkeleton />;
  if (error) return <ErrorBox message={error} onRetry={onRetry} />;

  // ----- Внутри выбранного плейлиста -----
  if (selected) {
    const items = selected.trackIds.map((id) => tracks.find((t) => t.id === id)).filter(Boolean);
    const icon = selected.system ? HeartFilledIcon : undefined;

    return (
      <>
        <button
          type="button"
          onClick={() => { setSelectedId(null); setEditing(false); }}
          className="mb-4 flex items-center gap-1 text-sm text-mist/70 transition hover:text-mist"
        >
          <BackIcon className="h-4 w-4" /> Your playlists
        </button>

        {editing ? (
          <PlaylistForm
            initial={{ name: selected.name, cover: selected.cover || "" }}
            submitLabel="Save changes"
            onSubmit={(data) => { onUpdate(selected.id, data); setEditing(false); }}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <div className="mb-6 flex flex-wrap items-center gap-4">
            <Cover id={selected.id} src={selected.cover} icon={icon} className="h-24 w-24 shrink-0 rounded-2xl md:h-32 md:w-32" />
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-2xl font-semibold text-mist">{selected.name}</h2>
              <p className="text-sm text-mist/60">{items.length} tracks</p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setAddingTracks(true)}
                className="flex items-center gap-2 rounded-full bg-violet px-4 py-2 text-sm text-mist shadow-[0_0_16px_rgba(139,95,191,0.45)] transition hover:brightness-110"
              >
                <PlusIcon className="h-4 w-4" /> Add tracks
              </button>
              {!selected.system && (
                <button
                  type="button"
                  onClick={() => setEditing(true)}
                  className="flex items-center gap-2 rounded-full border border-violet/50 px-4 py-2 text-sm text-mist transition hover:bg-violet/20"
                >
                  <PencilIcon className="h-4 w-4" /> Edit
                </button>
              )}
            </div>
          </div>
        )}

        {items.length === 0 ? (
          <EmptyState>This playlist is empty. Use “Add tracks” or find songs in Search.</EmptyState>
        ) : (
          <TrackList
            tracks={items}
            {...listProps}
            // В плейлисте у строки есть кнопка удаления (в «Liked Songs» отдельное сердце не нужно)
            renderActions={(track) =>
              listProps.renderActions(track, {
                hideLike: selected.system,
                hideAdd: true,
                onRemove: () => onRemoveTrack(selected.id, track.id),
              })
            }
          />
        )}

        {addingTracks && (
          <AddTracksModal
            tracks={tracks}
            playlist={selected}
            onToggle={(trackId) => onToggleTrack(selected.id, trackId)}
            onClose={() => setAddingTracks(false)}
          />
        )}
      </>
    );
  }

  // ----- Список плейлистов -----
  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold text-mist">Your playlists</h2>
        {!creating && (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="flex items-center gap-2 rounded-full bg-violet px-4 py-2 text-sm text-mist shadow-[0_0_16px_rgba(139,95,191,0.45)] transition hover:brightness-110"
          >
            <PlusIcon className="h-4 w-4" /> Create playlist
          </button>
        )}
      </div>

      {creating && (
        <PlaylistForm
          submitLabel="Create"
          onSubmit={(data) => { onCreate(data); setCreating(false); }}
          onCancel={() => setCreating(false)}
        />
      )}

      <ul className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-4">
        {playlists.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              onClick={() => setSelectedId(p.id)}
              className="w-full rounded-2xl p-2 text-left transition hover:bg-mist/5 focus-visible:outline-2 focus-visible:outline-violet"
            >
              <Cover
                id={p.id}
                src={p.cover}
                icon={p.system ? HeartFilledIcon : undefined}
                className="aspect-square w-full rounded-2xl"
              />
              <p className="mt-2 truncate font-medium text-mist">{p.name}</p>
              <p className="text-sm text-mist/60">{p.trackIds.length} tracks</p>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
