const stroke = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
};
const fill = { fill: "currentColor", "aria-hidden": true };

export const SearchIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke}>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </svg>
);

// Круг с «вырезанным» треугольником: работает на любом фоне кнопки
export const PlaylistIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...fill}>
    <path fillRule="evenodd" d="M12 1a11 11 0 1 0 0 22 11 11 0 0 0 0-22zM10 8v8l6-4z" />
  </svg>
);

export const HomeIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...fill}>
    <path d="M12 3 2 12h3v8h5v-5h4v5h5v-8h3z" />
  </svg>
);

export const PlayIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...fill}>
    <path d="M7 4.5v15l13-7.5z" />
  </svg>
);

export const PauseIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...fill}>
    <rect x="6" y="4" width="4" height="16" rx="1" />
    <rect x="14" y="4" width="4" height="16" rx="1" />
  </svg>
);

export const MusicNoteIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke}>
    <path d="M9 18V5l11-2v13" />
    <circle cx="6" cy="18" r="3" />
    <circle cx="17" cy="16" r="3" />
  </svg>
);

export const LogoutIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="m16 17 5-5-5-5M21 12H9" />
  </svg>
);

export const PlusIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke}>
    <path d="M12 5v14M5 12h14" />
  </svg>
);

export const BackIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke}>
    <path d="m15 18-6-6 6-6" />
  </svg>
);

export const EyeIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke}>
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

export const EyeOffIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke}>
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
    <path d="m1 1 22 22" />
  </svg>
);

export const PrevIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...fill}>
    <path d="M6 5h2v14H6zM20 5v14L9 12z" />
  </svg>
);

export const NextIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...fill}>
    <path d="M16 5h2v14h-2zM4 5v14l11-7z" />
  </svg>
);

export const UploadIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke}>
    <path d="M12 15V3m0 0L7 8m5-5 5 5M4 17v3h16v-3" />
  </svg>
);

export const PencilIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke}>
    <path d="M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z" />
  </svg>
);

export const HeartIcon = ({ className, filled = false }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke} fill={filled ? "currentColor" : "none"}>
    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
  </svg>
);

export const HeartFilledIcon = (props) => <HeartIcon filled {...props} />;

export const CheckIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke}>
    <path d="M20 6 9 17l-5-5" />
  </svg>
);

export const CloseIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke}>
    <path d="M18 6 6 18M6 6l12 12" />
  </svg>
);

export const TrashIcon = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} {...stroke}>
    <path d="M3 6h18M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6" />
  </svg>
);
