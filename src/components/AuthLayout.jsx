import ShaderBackground from "./ShaderBackground.jsx";

// Общая обёртка: анимированный фон, логотип MUSIC и стеклянная карточка по центру.
export default function AuthLayout({ children }) {
  return (
    <main className="auth-bg relative isolate flex min-h-screen flex-col items-center justify-center gap-8 px-4 py-10 font-sans">
      <ShaderBackground />

      <h1 className="font-display text-6xl tracking-tight text-mist drop-shadow-[0_0_14px_rgba(139,95,191,0.9)] sm:text-7xl">
        MUSIC
      </h1>

      <div className="w-full max-w-[21rem] rounded-[2.5rem] border border-violet/40 bg-card/90 px-8 py-8 shadow-[0_0_32px_rgba(139,95,191,0.35)] backdrop-blur-md">
        {children}
      </div>
    </main>
  );
}
