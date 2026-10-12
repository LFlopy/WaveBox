import { useState } from "react";
import { MusicNoteIcon } from "./icons.jsx";

// Число из id (id бывает и числом, и строкой), чтобы градиент был стабильным
const hashId = (id) =>
  typeof id === "number" ? id : [...String(id)].reduce((sum, ch) => sum + ch.charCodeAt(0), 0);

// Обложка: картинка, если есть src и она загрузилась, иначе фиолетовый градиент с иконкой.
export default function Cover({ id = 0, src, alt = "", className = "", icon: Icon = MusicNoteIcon }) {
  const [failedSrc, setFailedSrc] = useState(null);

  if (src && failedSrc !== src) {
    return (
      <img
        src={src}
        alt={alt}
        onError={() => setFailedSrc(src)}
        className={`object-cover ${className}`}
      />
    );
  }

  const hue = 250 + ((hashId(id) * 17) % 60);
  return (
    <div
      aria-hidden="true"
      className={`flex items-center justify-center text-mist/60 ${className}`}
      style={{
        background: `linear-gradient(135deg, hsl(${hue} 45% 38%), hsl(${hue + 20} 55% 18%))`,
      }}
    >
      <Icon className="h-1/2 w-1/2" />
    </div>
  );
}
