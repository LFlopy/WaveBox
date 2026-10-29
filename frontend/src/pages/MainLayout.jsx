import { useCallback, useEffect, useMemo, useState } from "react";
import Sidebar from "../components/Sidebar.jsx";
import Player from "../components/Player.jsx";
import TrackActions from "../components/TrackActions.jsx";
import PlaylistPickerModal from "../components/PlaylistPickerModal.jsx";
import HomeView from "../views/HomeView.jsx";
import PlaylistsView from "../views/PlaylistsView.jsx";
import SearchView from "../views/SearchView.jsx";
import { fetchTracks, fetchPlaylists, savePlaylists, LIKED_ID } from "../api/musicApi.js";
import { authApi } from "../api/authApi.js";

const newId = () => `pl-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`;

export default function MainLayout({ user, onLogout }) {
  const [activeTab, setActiveTab] = useState("home"); // "home" | "playlists" | "search"

  const [catalog, setCatalog] = useState([]); // все треки, доступные в поиске
  const [playlists, setPlaylists] = useState([]); // плейлисты пользователя
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");

  const [currentTrack, setCurrentTrack] = useState(null);
  const [queue, setQueue] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);

  const [pickerTrack, setPickerTrack] = useState(null); // трек, для которого открыто окно «Add to playlist»

  // «Запрос к бэкенду» при открытии экрана (и при нажатии Try again)
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    Promise.all([fetchTracks(), fetchPlaylists(user.name)])
      .then(([loadedTracks, loadedPlaylists]) => {
        if (cancelled) return;
        setCatalog(loadedTracks);
        setPlaylists(loadedPlaylists);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Couldn't load your library.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [reloadKey, user.name]);

  // Любое изменение плейлистов сохраняем (после первой загрузки)
  useEffect(() => {
    if (!loading && !error) savePlaylists(user.name, playlists);
  }, [playlists, loading, error, user.name]);

  // ----- Медиатека = все треки, которые лежат хотя бы в одном плейлисте -----
  const libraryTracks = useMemo(() => {
    const ids = new Set(playlists.flatMap((p) => p.trackIds));
    return catalog.filter((t) => ids.has(t.id));
  }, [playlists, catalog]);

  // ----- Работа с плейлистами -----
  const changeTracks = (playlistId, fn) =>
    setPlaylists((prev) =>
      prev.map((p) => (p.id === playlistId ? { ...p, trackIds: fn(p.trackIds) } : p))
    );

  const toggleTrack = (playlistId, trackId) =>
    changeTracks(playlistId, (ids) =>
      ids.includes(trackId) ? ids.filter((id) => id !== trackId) : [...ids, trackId]
    );

  const removeTrack = (playlistId, trackId) =>
    changeTracks(playlistId, (ids) => ids.filter((id) => id !== trackId));

  const likedIds = playlists.find((p) => p.id === LIKED_ID)?.trackIds ?? [];
  const isLiked = (trackId) => likedIds.includes(trackId);
  const toggleLike = (trackId) => toggleTrack(LIKED_ID, trackId);

  // firstTrackId: если передан, трек сразу попадает в новый плейлист
  const createPlaylist = ({ name, cover = "" }, firstTrackId) => {
    setPlaylists((prev) => [
      ...prev,
      { id: newId(), name, cover, trackIds: firstTrackId != null ? [firstTrackId] : [] },
    ]);
  };

  const updatePlaylist = (id, { name, cover }) =>
    setPlaylists((prev) => prev.map((p) => (p.id === id ? { ...p, name, cover } : p)));

  // ----- Воспроизведение -----
  const handleSelectTrack = (track, list = [track]) => {
    setQueue(list);
    if (currentTrack?.id === track.id) {
      setIsPlaying((p) => !p);
    } else {
      setCurrentTrack(track);
      setIsPlaying(true);
    }
  };

  const index = queue.findIndex((t) => t.id === currentTrack?.id);
  const canSkip = queue.length > 1;

  const playAt = (i) => {
    setCurrentTrack(queue[(i + queue.length) % queue.length]);
    setIsPlaying(true);
  };
  const handleNext = () => canSkip && playAt(index + 1);
  const handlePrev = () => canSkip && playAt(index - 1);

  const handleEnded = useCallback(() => {
    if (index >= 0 && index < queue.length - 1) {
      setCurrentTrack(queue[index + 1]);
      setIsPlaying(true);
    } else {
      setIsPlaying(false);
    }
  }, [index, queue]);

  const handleUpload = async (file) => {
    setUploading(true);
    setUploadMessage("Uploading...");
    try {
      const result = await authApi.uploadTrack(file);
      setCatalog(await fetchTracks());
      setUploadMessage(result.duplicate ? "This track is already in the library." : "Track uploaded successfully.");
      setActiveTab("search");
    } catch (err) {
      setUploadMessage(err.message || "Couldn't upload this track.");
    } finally {
      setUploading(false);
    }
  };

  // Кнопки в строке трека. По умолчанию: лайк и «+».
  // opts позволяет переопределить (например, в плейлисте: убрать «+» и добавить удаление).
  const renderActions = (track, opts = {}) => (
    <TrackActions
      liked={isLiked(track.id)}
      onLike={opts.hideLike ? undefined : () => toggleLike(track.id)}
      onAdd={opts.hideAdd ? undefined : () => setPickerTrack(track)}
      onRemove={opts.onRemove}
    />
  );

  const dataProps = { loading, error, onRetry: () => setReloadKey((k) => k + 1) };
  const listProps = {
    currentId: currentTrack?.id,
    isPlaying,
    onSelect: handleSelectTrack,
    renderActions,
  };

  return (
    <>
      <div className="grid h-dvh grid-cols-1 grid-rows-[auto_minmax(0,1fr)_auto] gap-3 p-3 font-sans text-mist md:grid-cols-[17rem_minmax(0,1fr)] md:grid-rows-[minmax(0,1fr)_auto] md:gap-4 md:p-6 lg:grid-cols-[21rem_minmax(0,1fr)]">
        <Sidebar
          activeTab={activeTab}
          onChange={setActiveTab}
          user={user}
          onLogout={onLogout}
          onUpload={handleUpload}
          uploading={uploading}
          uploadMessage={uploadMessage}
        />

        <section className="min-h-0 overflow-hidden rounded-3xl bg-ink/85 p-2 backdrop-blur-md md:p-3">
          <div className="scrollbar-dark h-full overflow-y-auto p-3 md:p-5">
            {activeTab === "home" && <HomeView tracks={libraryTracks} listProps={listProps} {...dataProps} />}
            {activeTab === "playlists" && (
              <PlaylistsView
                playlists={playlists}
                tracks={catalog}
                onCreate={createPlaylist}
                onUpdate={updatePlaylist}
                onToggleTrack={toggleTrack}
                onRemoveTrack={removeTrack}
                listProps={listProps}
                {...dataProps}
              />
            )}
            {activeTab === "search" && <SearchView tracks={catalog} listProps={listProps} {...dataProps} />}
          </div>
        </section>

        <Player
          track={currentTrack}
          isPlaying={isPlaying}
          canSkip={canSkip}
          onTogglePlay={() => setIsPlaying((p) => !p)}
          onPrev={handlePrev}
          onNext={handleNext}
          onEnded={handleEnded}
        />
      </div>

      {pickerTrack && (
        <PlaylistPickerModal
          track={pickerTrack}
          playlists={playlists}
          onToggle={toggleTrack}
          onCreate={(name, trackId) => createPlaylist({ name }, trackId)}
          onClose={() => setPickerTrack(null)}
        />
      )}
    </>
  );
}
