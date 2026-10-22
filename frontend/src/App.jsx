import { useState, useEffect } from "react";
import { authApi } from "./api/authApi.js";
import ShaderBackground from "./components/ShaderBackground.jsx";
import AuthLayout from "./components/AuthLayout.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import MainLayout from "./pages/MainLayout.jsx";

export default function App() {
  const [user, setUser] = useState(null); // null = не авторизован
  const [screen, setScreen] = useState("login"); // "login" | "register"
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    authApi
      .me()
      .then((userData) => {
        setUser({ name: userData.username });
      })
      .catch(() => {
        setUser(null);
      })
      .finally(() => {
        setCheckingAuth(false);
      });
  }, []);

  //Вход в аккаунт
  const handleLogin = async (values) => {
    const userData = await authApi.login(values);
    setUser({ name: userData.username });
  };

  //Регистраця
  const handleRegister = async (values) => {
    await authApi.register(values);

    setScreen("login");
  };

  //Выход из аккаунт
  const handleLogout = async () => {
    await authApi.logout();
    setUser(null);
    setScreen("login");
  };

  return (
    <div className="relative isolate">
      <ShaderBackground />

      {checkingAuth ? (
        <div className="min-h-screen flex items-center justify-center">
          <p className="text-white">Loading...</p>
        </div>
      ) : user ? (
        <MainLayout user={user} onLogout={handleLogout} />
      ) : (
        <AuthLayout>
          {screen === "login" ? (
            <Login
              onSubmit={handleLogin}
              onSwitch={() => setScreen("register")}
            />
          ) : (
            <Register
              onSubmit={handleRegister}
              onSwitch={() => setScreen("login")}
            />
          )}
        </AuthLayout>
      )}
    </div>
  );
}
