import { useState } from "react";
import TextField from "../components/TextField.jsx";
import SubmitButton from "../components/SubmitButton.jsx";

function validate({ username, password }) {
  const errors = {};
  if (!username.trim()) errors.username = "Enter your username";
  if (!password) errors.password = "Enter your password";
  else if (password.length < 6) errors.password = "At least 6 characters";
  return errors;
}

export default function Login({ onSubmit, onSwitch }) {
  const [values, setValues] = useState({ username: "", password: "" });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setValues((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: undefined })); // убираем ошибку при вводе
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const found = validate(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setLoading(true);
    setServerError("");
    try {
      await onSubmit(values);
    } catch (err) {
      setServerError(err.message || "Couldn't log in. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
      <TextField
        label="Username"
        name="username"
        autoComplete="username"
        value={values.username}
        onChange={handleChange}
        error={errors.username}
      />
      <TextField
        label="Password"
        name="password"
        type="password"
        autoComplete="current-password"
        value={values.password}
        onChange={handleChange}
        error={errors.password}
      />

      {serverError && (
        <p role="alert" className="text-center text-xs text-red-300">
          {serverError}
        </p>
      )}

      <div className="mt-2 px-3">
        <SubmitButton loading={loading}>Log in</SubmitButton>
      </div>

      <p className="text-center text-[11px] text-mist">
        Don't have an account?{" "}
        <button type="button" onClick={onSwitch} className="font-semibold underline-offset-2 hover:underline focus-visible:underline">
          Sign up
        </button>
      </p>
    </form>
  );
}
