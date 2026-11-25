import { useEffect, useState } from "react";
import { authApi } from "../api/authApi.js";

export default function TelegramAccount({ launch, signIn, onLogin }) {
  const [linked, setLinked] = useState(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (signIn) return;
    let current = true;
    authApi.telegramAccount()
      .then((data) => { if (current) setLinked(data.linked); })
      .catch((error) => { if (current) setMessage(error.message); });
    return () => { current = false; };
  }, [signIn]);

  async function submit() {
    setPending(true);
    setMessage("");
    try {
      if (signIn) {
        onLogin(await authApi.telegramLogin(launch));
      } else {
        const data = linked ? await authApi.unlinkTelegram() : await authApi.linkTelegram(launch);
        setLinked(data.linked);
        setMessage(data.linked ? "Telegram account linked." : "Telegram account unlinked.");
      }
    } catch (error) {
      setMessage(error.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="my-2 space-y-1 text-sm">
      {(signIn || linked !== null) && (
        <button
          type="button"
          disabled={pending}
          onClick={submit}
          className="rounded-xl border border-violet/50 px-3 py-2 text-mist transition hover:bg-violet/20 disabled:opacity-50"
        >
          {signIn ? "Sign in with Telegram" : linked ? "Unlink Telegram" : "Link Telegram"}
        </button>
      )}
      {message && <p role="status" className="text-mist/80">{message}</p>}
    </div>
  );
}
