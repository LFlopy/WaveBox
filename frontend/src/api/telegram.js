let loading;

export function loadTelegramLaunch() {
  if (window.Telegram?.WebApp?.initData) {
    window.Telegram.WebApp.ready();
    return Promise.resolve(window.Telegram.WebApp.initData);
  }
  const params = new URLSearchParams(window.location.hash.slice(1));
  if (!params.has("tgWebAppData")) return Promise.resolve("");

  loading ??= new Promise((resolve) => {
    const script = document.createElement("script");
    const finish = (data) => {
      clearTimeout(timeout);
      resolve(data);
    };
    const timeout = setTimeout(() => finish(""), 5000);
    script.src = "https://telegram.org/js/telegram-web-app.js";
    script.onload = () => {
      const app = window.Telegram?.WebApp;
      app?.ready();
      finish(app?.initData ?? "");
    };
    script.onerror = () => finish("");
    document.head.append(script);
  });
  return loading;
}
