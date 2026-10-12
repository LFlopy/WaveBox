import Logo from "./Logo.jsx";
import { SearchIcon, PlaylistIcon, HomeIcon, LogoutIcon } from "./icons.jsx";

const TABS = [
  { id: "search", label: "search", Icon: SearchIcon },
  { id: "playlists", label: "your playlists", Icon: PlaylistIcon },
  { id: "home", label: "home", Icon: HomeIcon },
];

export default function Sidebar({ activeTab, onChange, user, onLogout }) {
  return (
    <aside className="flex flex-wrap items-center gap-4 rounded-3xl bg-ink/80 p-4 backdrop-blur-md md:row-span-2 md:flex-col md:flex-nowrap md:items-stretch md:gap-0 md:p-8">
      <Logo className="order-1 text-3xl md:text-center md:text-4xl lg:text-5xl" />

      {/* На телефоне вкладки идут рядом, на десктопе столбиком внизу */}
      <nav aria-label="Main" className="order-3 grid w-full grid-cols-3 gap-2 md:mt-auto md:grid-cols-1 md:gap-5">
        {TABS.map(({ id, label, Icon }) => {
          const active = id === activeTab;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onChange(id)}
              aria-current={active ? "page" : undefined}
              className={`flex h-16 flex-col items-center justify-center gap-1 rounded-2xl text-xs transition
                focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mist
                md:h-[4.5rem] md:flex-row md:justify-start md:gap-5 md:px-5 md:text-xl
                ${
                  active
                    ? "bg-mist text-violet shadow-[0_0_28px_rgba(232,223,236,0.55)]"
                    : "bg-violet/70 text-mist hover:bg-violet/85"
                }`}
            >
              <Icon className="h-6 w-6 shrink-0 md:h-8 md:w-8" />
              <span>{label}</span>
            </button>
          );
        })}
      </nav>

      <div className="order-2 ml-auto flex items-center gap-3 md:order-3 md:ml-0 md:mt-10">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-mist text-lg font-semibold uppercase text-violet md:h-16 md:w-16 md:text-2xl">
          {user.name.charAt(0)}
        </div>
        <span className="hidden max-w-[8rem] truncate text-mist sm:inline md:max-w-none md:flex-1 md:text-xl">
          {user.name}
        </span>
        <button
          type="button"
          onClick={onLogout}
          aria-label="Log out"
          className="rounded-full p-2 text-mist/60 transition hover:bg-mist/10 hover:text-mist focus-visible:outline-2 focus-visible:outline-violet"
        >
          <LogoutIcon className="h-5 w-5" />
        </button>
      </div>
    </aside>
  );
}
