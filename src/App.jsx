import { useState } from "react";
import ShaderBackground from "./components/ShaderBackground.jsx";
import AuthLayout from "./components/AuthLayout.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import MainLayout from "./pages/MainLayout.jsx";

// Временная заглушка вместо бэкенда. Когда API будет готово — замени тело
// на fetch("/api/login", { method: "POST", body: JSON.stringify(values) ... })
// и бросай Error с текстом ошибки, если ответ не ok.
const fakeRequest = (values) =>
  new Promise((resolve) => {
    setTimeout(() => {
      console.log("Отправлено на сервер:", values);
      resolve();
    }, 1500);
  });

export default function App() {
  const [user, setUser] = useState(null); // null = не авторизован
  const [screen, setScreen] = useState("login"); // "login" | "register"

  const handleAuth = async (values) => {
    await fakeRequest(values);
    setUser({ name: values.username });
  };

  const handleLogout = () => {
    setUser(null);
    setScreen("login");
  };

  return (
    <div className="relative isolate">
      {/* Фон один на всё приложение: при смене экранов он не перезапускается */}
      <ShaderBackground />

      {user ? (
        <MainLayout user={user} onLogout={handleLogout} />
      ) : (
        <AuthLayout>
          {screen === "login" ? (
            <Login onSubmit={handleAuth} onSwitch={() => setScreen("register")} />
          ) : (
            <Register onSubmit={handleAuth} onSwitch={() => setScreen("login")} />
          )}
        </AuthLayout>
      )}
    </div>
  );
}
