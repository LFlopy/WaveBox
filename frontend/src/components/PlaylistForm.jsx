import { useState } from "react";
import Cover from "./Cover.jsx";
import { UploadIcon } from "./icons.jsx";

const MAX_FILE_MB = 5;

const inputClass =
  "h-10 w-full rounded-xl border border-violet/40 bg-ink px-3 text-sm text-mist outline-none transition placeholder:text-mist/40 focus:border-violet focus:ring-2 focus:ring-violet/50";

// Подходит ссылка http(s) или путь к файлу из public/, например /covers/cat.jpg
function isValidCover(value) {
  if (!value || value.startsWith("data:") || value.startsWith("/")) return true;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

// Уменьшаем картинку до 400 px и сжимаем в JPEG, чтобы она весила десятки КБ
// (так плейлисты спокойно помещаются в localStorage).
function resizeImage(file, maxSize = 400) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const w = img.width || maxSize;
      const h = img.height || maxSize;
      const scale = Math.min(1, maxSize / Math.max(w, h));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(w * scale);
      canvas.height = Math.round(h * scale);
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#282033"; // фон под прозрачные PNG
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Bad image"));
    };
    img.src = url;
  });
}

export default function PlaylistForm({ initial = { name: "", cover: "" }, submitLabel, onSubmit, onCancel }) {
  const [name, setName] = useState(initial.name);
  const [cover, setCover] = useState(initial.cover); // ссылка, путь или data:-картинка из файла
  const [urlInput, setUrlInput] = useState(initial.cover.startsWith("data:") ? "" : initial.cover);
  const [errors, setErrors] = useState({});

  const handleUrlChange = (e) => {
    setUrlInput(e.target.value);
    setCover(e.target.value.trim());
    setErrors((prev) => ({ ...prev, cover: undefined }));
  };

  const handleFile = (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // чтобы можно было выбрать тот же файл повторно
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      setErrors((prev) => ({ ...prev, cover: "Choose an image file" }));
      return;
    }
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      setErrors((prev) => ({ ...prev, cover: `Image must be smaller than ${MAX_FILE_MB} MB` }));
      return;
    }

    // С бэкендом здесь будет отправка исходного файла через FormData.
    resizeImage(file)
      .then((dataUrl) => {
        setCover(dataUrl);
        setUrlInput("");
        setErrors((prev) => ({ ...prev, cover: undefined }));
      })
      .catch(() => setErrors((prev) => ({ ...prev, cover: "Couldn't read this image" })));
  };

  const handleRemove = () => {
    setCover("");
    setUrlInput("");
    setErrors((prev) => ({ ...prev, cover: undefined }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const found = {};
    if (!name.trim()) found.name = "Enter a name";
    if (!isValidCover(cover)) found.cover = "Use an http(s) link or a path like /covers/cat.jpg";
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    onSubmit({ name: name.trim(), cover });
  };

  return (
    <form
      onSubmit={handleSubmit}
      noValidate
      className="mb-6 flex flex-col gap-4 rounded-2xl border border-violet/30 bg-mist/5 p-4 sm:flex-row"
    >
      <Cover src={cover} className="h-28 w-28 shrink-0 self-center rounded-2xl sm:self-start" />

      <div className="min-w-0 flex-1 space-y-3">
        <div>
          <input
            autoFocus
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setErrors((prev) => ({ ...prev, name: undefined }));
            }}
            placeholder="Playlist name"
            aria-label="Playlist name"
            className={inputClass}
          />
          {errors.name && <p className="mt-1 pl-1 text-xs text-red-300">{errors.name}</p>}
        </div>

        <div>
          <input
            value={urlInput}
            onChange={handleUrlChange}
            placeholder="Cover link (https://… or /covers/cat.jpg)"
            aria-label="Cover link"
            className={inputClass}
          />
          {errors.cover && <p className="mt-1 pl-1 text-xs text-red-300">{errors.cover}</p>}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="flex cursor-pointer items-center gap-2 rounded-full border border-violet/50 px-4 py-2 text-sm text-mist transition hover:bg-violet/20 focus-within:outline-2 focus-within:outline-violet">
            <UploadIcon className="h-4 w-4" />
            Choose file
            <input type="file" accept="image/*" onChange={handleFile} className="sr-only" />
          </label>
          {cover && (
            <button type="button" onClick={handleRemove} className="px-2 text-sm text-mist/70 transition hover:text-mist">
              Remove cover
            </button>
          )}
        </div>

        <div className="flex gap-2 pt-1">
          <button type="submit" className="rounded-full bg-violet px-5 py-2 text-sm text-mist transition hover:brightness-110">
            {submitLabel}
          </button>
          <button type="button" onClick={onCancel} className="rounded-full px-4 py-2 text-sm text-mist/70 transition hover:text-mist">
            Cancel
          </button>
        </div>
      </div>
    </form>
  );
}
