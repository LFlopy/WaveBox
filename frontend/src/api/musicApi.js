import { mockTracks } from "../data/mockTracks.js";

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// Системный плейлист, который создаётся каждому новому пользователю
export const LIKED_ID = "liked";
export const LIKED_NAME = "Liked Songs";

const createDefaultPlaylists = () => [
  { id: LIKED_ID, name: LIKED_NAME, cover: "", system: true, trackIds: [] },
];

// Гарантируем, что системный плейлист на месте, даже если данные повреждены
const ensureLiked = (list) =>
  list.some((p) => p.id === LIKED_ID) ? list : [...createDefaultPlaylists(), ...list];

const storageKey = (username) => `music-app:playlists:${username.trim().toLowerCase()}`;

// КАТАЛОГ: все треки, которые можно найти в поиске (из src/data/mockTracks.js).
// С бэкендом: const res = await fetch("/api/tracks"); return res.json();
export async function fetchTracks() {
  await delay(1200);
  return mockTracks;
}

// ПЛЕЙЛИСТЫ ПОЛЬЗОВАТЕЛЯ.
// Пока бэкенда нет, храним их в localStorage браузера отдельно для каждого логина.
// Если данных нет — это первый вход: создаём пустой «Liked Songs».
// С бэкендом: const res = await fetch("/api/playlists"); return res.json();
export async function fetchPlaylists(username) {
  await delay(900);
  try {
    const raw = localStorage.getItem(storageKey(username));
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return ensureLiked(parsed);
    }
  } catch {
    /* повреждённые данные игнорируем и начинаем с чистого листа */
  }
  return createDefaultPlaylists();
}

// С бэкендом: fetch("/api/playlists", { method: "PUT", body: JSON.stringify(playlists) })
export async function savePlaylists(username, playlists) {
  try {
    localStorage.setItem(storageKey(username), JSON.stringify(playlists));
  } catch (err) {
    console.warn("Couldn't save playlists:", err);
  }
}
