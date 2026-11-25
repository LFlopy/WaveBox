import { useEffect, useMemo, useState } from "react";
import { authApi } from "../api/authApi.js";
import TrackList from "./TrackList.jsx";

const buttonClass = "rounded-xl border border-violet/50 px-3 py-2 text-sm transition hover:bg-violet/20 disabled:opacity-50";
const inputClass = "rounded-xl border border-violet/40 bg-ink px-3 py-2 text-sm";

async function findSources(entry) {
  const encoder = new TextEncoder();
  let search = "";
  for (const character of `${entry.title} ${entry.artist}`.trim()) {
    if (encoder.encode(search + character).length > 200) break;
    search += character;
  }
  const query = new URLSearchParams({ sources: "internet_archive,jamendo", q: search.trim(), limit: "8" });
  const response = await fetch(`/api/external/search?${query}`);
  if (!response.ok) throw new Error("External search is temporarily unavailable.");
  return response.json();
}

function safeLink(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : undefined;
  } catch {
    return undefined;
  }
}

function archiveId(pageUrl) {
  const match = safeLink(pageUrl)?.match(/^https:\/\/archive\.org\/details\/([\w.-]+)\/?$/);
  return match?.[1];
}

function MissingTrackSources({ entry, refreshCatalog }) {
  const [results, setResults] = useState(null);
  const [files, setFiles] = useState(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(action) {
    setBusy(true);
    setStatus("");
    try {
      await action();
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  if (!entry.title || !entry.artist) return null;

  return (
    <div className="mt-2 space-y-2">
      <button type="button" className={buttonClass} disabled={busy} onClick={() => run(async () => {
        const data = await findSources(entry);
        setResults(data.results.flatMap((result) =>
          result.variants.filter((variant) => variant.source === "internet_archive" || variant.source === "jamendo")
            .map((variant) => ({ ...variant, title: result.title, artist: result.artist })),
        ));
        setFiles(null);
        if (data.errors?.length) setStatus("Some sources are temporarily unavailable.");
      })}>Find sources</button>
      {results?.length === 0 && <p className="text-sm text-mist/60">No external results.</p>}
      {results?.map((result, index) => {
        const identifier = result.source === "internet_archive" && archiveId(result.pageUrl);
        const download = result.downloadAvailable && safeLink(result.downloadUrl);
        const destination = download || safeLink(result.pageUrl);
        return (
          <div key={`${result.source}-${index}`} className="flex flex-wrap items-center gap-2 text-sm">
            <span>{result.title} — {result.artist} ({result.source})</span>
            {identifier && <button type="button" className={buttonClass} disabled={busy} onClick={() => run(async () => {
              const response = await fetch(`/api/external/internet-archive/files?identifier=${encodeURIComponent(identifier)}`);
              if (!response.ok) throw new Error("Archive files are temporarily unavailable.");
              setFiles(await response.json());
            })}>List Archive files</button>}
            {destination && <a href={destination} target="_blank" rel="noreferrer" className="underline">
              {download ? "Download" : "Open source"}
            </a>}
          </div>
        );
      })}
      {files && (
        <div className="space-y-2 rounded-xl bg-mist/5 p-3">
          <p className="text-sm">{files.title}</p>
          {safeLink(files.licenseUrl) && <a href={safeLink(files.licenseUrl)} className="text-sm underline" target="_blank" rel="noreferrer">License</a>}
          {files.files.filter((file) => file.downloadAvailable).map((file) =>
            <button key={file.fileName} type="button" className={`${buttonClass} block`} disabled={busy} onClick={() => run(async () => {
              await authApi.importArchiveFile(files.identifier, file.fileName);
              await refreshCatalog();
              setStatus("Audio imported. Recheck the playlist to match it.");
            })}>Import {file.fileName}</button>
          )}
          {!files.files.some((file) => file.downloadAvailable) && <p className="text-sm">No eligible audio files.</p>}
        </div>
      )}
      {status && <p role="status" className="text-sm">{status}</p>}
    </div>
  );
}

export default function ImportedPlaylists({ tracks, listProps, refreshCatalog }) {
  const [playlists, setPlaylists] = useState([]);
  const [selected, setSelected] = useState(null);
  const [playlistId, setPlaylistId] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    authApi.importedPlaylists()
      .then((data) => { if (active) setPlaylists(data.playlists); })
      .catch((error) => { if (active) setMessage(error.message); });
    return () => { active = false; };
  }, []);

  const catalog = useMemo(() => new Map(tracks.map((track) => [track.id, track])), [tracks]);
  const matched = useMemo(() => selected?.entries.map((entry) => catalog.get(entry.trackId)).filter(Boolean) ?? [], [selected, catalog]);

  async function apply(action) {
    setBusy(true);
    setMessage("");
    try {
      const playlist = await action();
      setSelected(playlist);
      setPlaylists((previous) => [playlist, ...previous.filter(({ id }) => id !== playlist.id)]);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  function sync(remote) {
    const requestToken = token;
    if (remote) setToken("");
    apply(() => authApi.syncPlaylist(selected.id, selected.revision, remote, requestToken));
  }

  return (
    <section className="mt-6 space-y-3 border-t border-violet/35 pt-4">
      <h3 className="text-lg font-semibold">Imported playlists</h3>
      <label className="block text-sm">
        <span className="block pb-1">CSV or JSPF file</span>
        <input type="file" accept=".csv,.jspf,.json" disabled={busy} onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) apply(() => authApi.importPlaylistFile(file));
          event.target.value = "";
        }} />
      </label>
      <form className="flex flex-wrap items-end gap-2" onSubmit={(event) => {
        event.preventDefault();
        const requestToken = token;
        setToken("");
        apply(() => authApi.importListenBrainz(playlistId.trim(), requestToken));
      }}>
        <label className="text-sm">
          <span className="block pb-1">ListenBrainz playlist UUID</span>
          <input className={inputClass} value={playlistId} onChange={(event) => setPlaylistId(event.target.value)} required maxLength={36} />
        </label>
        <label className="text-sm">
          <span className="block pb-1">ListenBrainz token (private playlists)</span>
          <input className={inputClass} type="password" value={token} onChange={(event) => setToken(event.target.value)} autoComplete="off" maxLength={128} />
        </label>
        <button className={buttonClass} disabled={busy}>Import from ListenBrainz</button>
      </form>
      {message && <p role="alert" className="text-sm text-red-300">{message}</p>}
      {busy && <p role="status" className="text-sm">Updating playlist…</p>}
      <div className="flex flex-wrap gap-2">
        {playlists.map((playlist) => (
          <button key={playlist.id} type="button" className={buttonClass} aria-pressed={selected?.id === playlist.id} disabled={busy}
            onClick={() => apply(() => authApi.importedPlaylist(playlist.id))}>{playlist.name}</button>
        ))}
      </div>
      {selected && (
        <div className="space-y-3 rounded-2xl bg-mist/5 p-3">
          <h4 className="font-medium">{selected.name}</h4>
          <p className="text-sm text-mist/70">
            {selected.counts.matched} matched · {selected.counts.ambiguous} need review · {selected.counts.missing} missing
          </p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className={buttonClass} disabled={busy} onClick={() => sync(false)}>Recheck library</button>
            {selected.source === "file" && <label className="text-sm">
              <span className="block">Replace export file</span>
              <input type="file" accept=".csv,.jspf,.json" disabled={busy} onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) apply(() => authApi.replacePlaylistFile(selected.id, selected.revision, file));
                event.target.value = "";
              }} />
            </label>}
            {selected.source === "listenbrainz" && <button type="button" className={buttonClass} disabled={busy} onClick={() => sync(true)}>Sync ListenBrainz</button>}
          </div>
          {matched.length > 0 && <TrackList tracks={matched} {...listProps} />}
          <ol className="space-y-2">
            {selected.entries.map((entry, index) => entry.trackId == null && (
              <li key={`${selected.id}-${index}-${entry.recordingMbid ?? entry.title}-${entry.artist}`} className="rounded-xl border border-violet/30 p-3">
                <p className="text-sm">{index + 1}. {entry.title || entry.recordingMbid}{entry.artist && ` — ${entry.artist}`}</p>
                {entry.status === "ambiguous" ? (
                  <select aria-label={`Match for entry ${index + 1}`} value="" disabled={busy} className={`${inputClass} mt-1 max-w-full`} onChange={(event) => {
                    if (event.target.value) apply(() => authApi.resolvePlaylistEntry(selected.id, selected.revision, index, Number(event.target.value)));
                  }}>
                    <option value="">Choose a local version</option>
                    {entry.candidateIds.map((id) => catalog.has(id) && (
                      <option key={id} value={id}>{catalog.get(id).title} — {catalog.get(id).artist} ({catalog.get(id).format || catalog.get(id).duration}, #{id})</option>
                    ))}
                  </select>
                ) : <MissingTrackSources entry={entry} refreshCatalog={refreshCatalog} />}
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
