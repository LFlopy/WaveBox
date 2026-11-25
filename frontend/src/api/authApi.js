const API_URL = "/api/auth";

function getCookie(name) {
  const cookies = document.cookie.split("; ");

  const cookie = cookies.find((item) => item.startsWith(`${name}=`));

  return cookie ? decodeURIComponent(cookie.split("=")[1]) : null;
}

async function request(endpoint, options = {}) {
  const response = await fetch(`${API_URL}/${endpoint}`, {
    credentials: "same-origin",
    ...options,
  });

  const data = await response.json();

  if (!response.ok) {
    throw new Error(
      Array.isArray(data.error)
        ? data.error.join(", ")
        : data.error || "Request failed",
    );
  }

  return data;
}

async function ensureCsrf() {
  await request("csrf");
}

async function post(endpoint, payload, headers = {}) {
  await ensureCsrf();

  const response = await request(endpoint, {
    method: "POST",
    headers: {
      ...headers,
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken") ?? "",
    },
    body: JSON.stringify(payload),
  });

  return response;
}

async function uploadFile(endpoint, file, headers = {}, fields = {}) {
  await ensureCsrf();
  const formData = new FormData();
  formData.append("file", file);
  for (const [key, value] of Object.entries(fields)) formData.append(key, value);
  return request(endpoint, {
    method: "POST",
    headers: {
      ...headers,
      "X-CSRFToken": getCookie("csrftoken") ?? "",
    },
    body: formData,
  });
}

async function waitForImport(result) {
  const deadline = Date.now() + 300000;
  while (result.status === "pending") {
    if (Date.now() >= deadline) {
      throw new Error("Import is still running. Refresh the library later.");
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
    result = await request(`imports/${result.importId}`);
  }
  return result;
}

export const authApi = {
  register: (values) => post("register", values),
  login: (values) => post("login", values),
  logout: () => post("logout", {}),
  me: () => request("me"),
  telegramLogin: (initData) => post("telegram/login", { initData }),
  telegramAccount: () => request("telegram/account"),
  linkTelegram: (initData) => post("telegram/account", { initData }),
  unlinkTelegram: async () => {
    await ensureCsrf();
    return request("telegram/account", {
      method: "DELETE",
      headers: { "X-CSRFToken": getCookie("csrftoken") ?? "" },
    });
  },
  uploadTrack: async (file) => waitForImport(await uploadFile("upload", file, { Prefer: "respond-async" })),
  importedPlaylists: () => request("playlists/imported"),
  importedPlaylist: (id) => request(`playlists/imported/${id}`),
  importPlaylistFile: (file) => uploadFile("playlists/imported", file),
  importListenBrainz: (playlistId, token) => post("playlists/imported", { playlistId, token }),
  syncPlaylist: (id, revision, remote, token) =>
    post(`playlists/imported/${id}/sync`, { revision, remote, token }),
  replacePlaylistFile: (id, revision, file) =>
    uploadFile(`playlists/imported/${id}/sync`, file, {}, { revision }),
  resolvePlaylistEntry: (id, revision, index, trackId) =>
    post(`playlists/imported/${id}/resolve`, { revision, index, trackId }),
  importArchiveFile: async (identifier, fileName) =>
    waitForImport(await post("external/internet-archive/download", { identifier, fileName }, { Prefer: "respond-async" })),
};
