import { useState } from "react";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";

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
  const [screen, setScreen] = useState("login"); // "login" | "register"

  return screen === "login" ? (
    <Login onSubmit={fakeRequest} onSwitch={() => setScreen("register")} />
  ) : (
    <Register onSubmit={fakeRequest} onSwitch={() => setScreen("login")} />
  );
}
