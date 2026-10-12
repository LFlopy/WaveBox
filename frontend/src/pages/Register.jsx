import { useState } from "react";
import TextField from "../components/TextField.jsx";
import SubmitButton from "../components/SubmitButton.jsx";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validate({ username, email, password, confirmPassword }) {
  const errors = {};
  if (username.trim().length < 3) errors.username = "At least 3 characters";
  if (!EMAIL_RE.test(email)) errors.email = "Enter a valid email";
  if (password.length < 6) errors.password = "At least 6 characters";
  if (confirmPassword !== password) errors.confirmPassword = "Passwords don't match";
  return errors;
}

export default function Register({ onSubmit, onSwitch }) {
  const [values, setValues] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [errors, setErrors] = useState({});
  const [serverError, setServerError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setValues((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => ({ ...prev, [name]: undefined }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const found = validate(values);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setLoading(true);
    setServerError("");
    try {
      // confirmPassword бэкенду обычно не нужен — отправляем без него
      const { confirmPassword, ...payload } = values;
      await onSubmit(payload);
    } catch (err) {
      setServerError(err.message || "Couldn't create the account. Try again.");
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
        label="Email"
        name="email"
        type="email"
        autoComplete="email"
        value={values.email}
        onChange={handleChange}
        error={errors.email}
      />
      <TextField
        label="Password"
        name="password"
        type="password"
        autoComplete="new-password"
        value={values.password}
        onChange={handleChange}
        error={errors.password}
      />
      <TextField
        label="Confirm Password"
        name="confirmPassword"
        type="password"
        autoComplete="new-password"
        value={values.confirmPassword}
        onChange={handleChange}
        error={errors.confirmPassword}
      />

      {serverError && (
        <p role="alert" className="text-center text-xs text-red-300">
          {serverError}
        </p>
      )}

      <div className="mt-2 px-3">
        <SubmitButton loading={loading}>Create Account</SubmitButton>
      </div>

      <p className="text-center text-[11px] text-mist">
        Already have an account?{" "}
        <button type="button" onClick={onSwitch} className="font-semibold underline-offset-2 hover:underline focus-visible:underline">
          Log in
        </button>
      </p>
    </form>
  );
}
