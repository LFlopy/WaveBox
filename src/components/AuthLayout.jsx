import Logo from "./Logo.jsx";

// Логотип прижат к верху и не двигается при смене карточки.
// Фон здесь не рисуется: он живёт в App.jsx и не перезапускается.
export default function AuthLayout({ children }) {
  return (
    <main className="flex min-h-dvh flex-col items-center gap-8 px-4 pb-10 pt-[10vh] font-sans">
      <h1>
        <Logo className="text-6xl sm:text-7xl" />
      </h1>

      <div className="w-full max-w-[21rem] rounded-[2.5rem] border border-violet/40 bg-card/90 px-8 py-8 shadow-[0_0_32px_rgba(139,95,191,0.35)] backdrop-blur-md">
        {children}
      </div>
    </main>
  );
}
