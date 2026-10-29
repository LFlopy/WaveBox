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

async function post(endpoint, payload) {
  await ensureCsrf();

  const response = await request(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": getCookie("csrftoken") ?? "",
    },
    body: JSON.stringify(payload),
  });

  return response;
}

async function uploadTrack(file) {
  await ensureCsrf();
  const formData = new FormData();
  formData.append("file", file);
  return request("upload", {
    method: "POST",
    headers: {
      "X-CSRFToken": getCookie("csrftoken") ?? "",
    },
    body: formData,
  });
}

export const authApi = {
  register: (values) => post("register", values),
  login: (values) => post("login", values),
  logout: () => post("logout", {}),
  me: () => request("me"),
  uploadTrack,
};
