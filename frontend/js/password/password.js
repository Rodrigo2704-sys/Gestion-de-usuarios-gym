/* Lógica de las pantallas: olvidé mi contraseña, crear nueva contraseña y cambiar contraseña.
   Ajusta las constantes de abajo a tu proyecto. */
(() => {
  "use strict";

  // ----------------------------------------------------------- configuración
  const API_BASE = window.API_BASE || "http://127.0.0.1:8000";   // <- AJUSTA: la misma dirección de tu API FastAPI (la que usa api-base.js)
  const API = API_BASE + "/api/password";
  const TOKEN_KEY = "token";                      // clave de localStorage donde tu login guarda el JWT
  const LOGIN_URL = "login.html";                 // a dónde mandar si no hay sesión

  // ---------------------------------------------------------------- helpers
  const $ = (selector, root = document) => root.querySelector(selector);
  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function showAlert(type, message) {
    const el = $("#alert");
    if (!el) return;
    el.className = "alert " + type;
    el.textContent = message;
    el.hidden = false;
  }

  function clearAlert() {
    const el = $("#alert");
    if (el) { el.hidden = true; el.textContent = ""; }
  }

  function setBusy(button, busy, busyText) {
    if (!button) return;
    if (busy) {
      button.dataset.label = button.textContent;
      button.textContent = busyText;
      button.disabled = true;
    } else {
      button.textContent = button.dataset.label || button.textContent;
      button.disabled = false;
    }
  }

  function markInvalid(input, invalid) {
    if (input) input.setAttribute("aria-invalid", invalid ? "true" : "false");
  }

  /** Convierte la respuesta de error de FastAPI (texto o lista de validaciones) en un mensaje legible. */
  function extractError(data, fallback) {
    if (!data || !data.detail) return fallback;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      const msgs = data.detail
        .map((e) => String(e.msg || "").replace(/^Value error,\s*/i, ""))
        .filter(Boolean);
      return msgs.length ? msgs.join(" ") : fallback;
    }
    return fallback;
  }

  async function post(path, body, { auth = false } = {}) {
    const headers = { "Content-Type": "application/json" };
    if (auth) {
      const token = localStorage.getItem(TOKEN_KEY);
      if (token) headers.Authorization = "Bearer " + token;
    }
    let res;
    try {
      res = await fetch(API + path, { method: "POST", headers, body: JSON.stringify(body) });
    } catch (_) {
      return { ok: false, status: 0, data: null };
    }
    let data = null;
    try { data = await res.json(); } catch (_) { /* respuesta sin cuerpo JSON */ }
    return { ok: res.ok, status: res.status, data };
  }

  const NETWORK_ERROR = "No pudimos conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.";

  // ------------------------------------- mostrar/ocultar y medidor de seguridad
  function bindToggles() {
    document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const input = document.getElementById(btn.dataset.togglePassword);
        if (!input) return;
        const show = input.type === "password";
        input.type = show ? "text" : "password";
        btn.textContent = show ? "Ocultar" : "Mostrar";
        btn.setAttribute("aria-label", show ? "Ocultar contraseña" : "Mostrar contraseña");
      });
    });
  }

  // Estas reglas deben coincidir con validate_password_strength() en app/schemas.py
  function checkRules(pw) {
    return {
      length: pw.length >= 8,
      letter: /[A-Za-z]/.test(pw),
      number: /\d/.test(pw),
      bytes: new TextEncoder().encode(pw).length <= 72,
    };
  }

  function strengthLevel(pw) {
    if (!pw) return 0;
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++;
    if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) score++;
    return Math.max(1, score);
  }

  function bindStrengthMeter(input) {
    const meter = $("#meter");
    const bar = $("#meter-bar");
    const label = $("#meter-label");
    const rules = document.querySelectorAll("#rules li");
    if (!input || !meter) return;
    const labels = ["", "Débil", "Aceptable", "Buena", "Muy buena"];

    input.addEventListener("input", () => {
      const pw = input.value;
      const level = strengthLevel(pw);
      meter.dataset.level = String(level);
      bar.style.width = (level * 25) + "%";
      label.textContent = labels[level];
      const result = checkRules(pw);
      rules.forEach((li) => li.classList.toggle("ok", !!result[li.dataset.rule]));
    });
  }

  /** Validaciones del lado del cliente (el servidor vuelve a validar todo). Devuelve un mensaje o null. */
  function validatePasswords(newPw, confirmPw) {
    const r = checkRules(newPw);
    if (!r.length) return "La contraseña debe tener al menos 8 caracteres.";
    if (!r.bytes) return "La contraseña es demasiado larga.";
    if (!r.letter || !r.number) return "La contraseña debe incluir al menos una letra y un número.";
    if (newPw !== confirmPw) return "Las contraseñas no coinciden.";
    return null;
  }

  // ------------------------------------------------- pantalla: olvidé mi clave
  function initForgot() {
    const form = $("#forgot-form");
    const emailInput = $("#email");
    const btn = $("#submit-btn");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      clearAlert();
      const email = emailInput.value.trim();
      if (!EMAIL_RE.test(email)) {
        markInvalid(emailInput, true);
        showAlert("error", "Escribe un correo válido.");
        return;
      }
      markInvalid(emailInput, false);

      setBusy(btn, true, "Enviando…");
      const res = await post("/forgot", { email });
      setBusy(btn, false);

      if (res.ok) {
        showAlert("success", res.data.message);
        form.reset();
      } else if (res.status === 0) {
        showAlert("error", NETWORK_ERROR);
      } else {
        showAlert("error", extractError(res.data, "No pudimos procesar la solicitud. Inténtalo más tarde."));
      }
    });
  }

  // ------------------------------------- pantalla: crear nueva contraseña (enlace)
  function readTokenFromUrl() {
    // El token viaja en el fragmento (#token=...) y lo borramos de la barra de direcciones.
    const params = new URLSearchParams(window.location.hash.replace(/^#/, ""));
    const token = params.get("token");
    if (window.location.hash) {
      history.replaceState(null, "", window.location.pathname);
    }
    return token;
  }

  function showState(name) {
    ["loading", "invalid", "form", "success"].forEach((s) => {
      const el = document.getElementById("state-" + s);
      if (el) el.hidden = s !== name;
    });
  }

  async function initReset() {
    const token = readTokenFromUrl();
    if (!token) { showState("invalid"); return; }

    const check = await post("/reset/validate", { token });
    if (!check.ok || !check.data || !check.data.valid) {
      showState("invalid");
      return;
    }
    showState("form");

    const form = $("#reset-form");
    const newInput = $("#new_password");
    const confirmInput = $("#confirm_password");
    const btn = $("#submit-btn");
    bindToggles();
    bindStrengthMeter(newInput);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      clearAlert();
      const problem = validatePasswords(newInput.value, confirmInput.value);
      markInvalid(newInput, !!problem);
      markInvalid(confirmInput, !!problem);
      if (problem) { showAlert("error", problem); return; }

      setBusy(btn, true, "Guardando…");
      const res = await post("/reset", {
        token,
        new_password: newInput.value,
        confirm_password: confirmInput.value,
      });
      setBusy(btn, false);

      if (res.ok) {
        newInput.value = "";
        confirmInput.value = "";
        showState("success");
      } else if (res.status === 0) {
        showAlert("error", NETWORK_ERROR);
      } else if (res.status === 400 && res.data && /enlace/i.test(String(res.data.detail))) {
        showState("invalid"); // el token venció o ya se usó mientras escribía
      } else {
        showAlert("error", extractError(res.data, "No pudimos guardar la contraseña. Inténtalo de nuevo."));
      }
    });
  }

  // ------------------------------------------------ pantalla: cambiar contraseña
  function initChange() {
    if (!localStorage.getItem(TOKEN_KEY)) {
      window.location.replace(LOGIN_URL);
      return;
    }

    const form = $("#change-form");
    const currentInput = $("#current_password");
    const newInput = $("#new_password");
    const confirmInput = $("#confirm_password");
    const btn = $("#submit-btn");
    bindToggles();
    bindStrengthMeter(newInput);

    // El enlace "Volver" depende del rol: admin -> usuarios.html, cliente -> cliente.html
    const volver = $("#volver");
    const rol = String(localStorage.getItem("rol_usuario") || "").trim().toLowerCase();
    if (volver && (rol === "admin" || rol === "administrador")) volver.href = "usuarios.html";

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      clearAlert();

      if (!currentInput.value) {
        markInvalid(currentInput, true);
        showAlert("error", "Escribe tu contraseña actual.");
        return;
      }
      markInvalid(currentInput, false);

      const problem = validatePasswords(newInput.value, confirmInput.value);
      markInvalid(newInput, !!problem);
      markInvalid(confirmInput, !!problem);
      if (problem) { showAlert("error", problem); return; }
      if (newInput.value === currentInput.value) {
        showAlert("error", "La nueva contraseña debe ser diferente a la actual.");
        return;
      }

      setBusy(btn, true, "Guardando…");
      const res = await post(
        "/change",
        {
          current_password: currentInput.value,
          new_password: newInput.value,
          confirm_password: confirmInput.value,
        },
        { auth: true }
      );
      setBusy(btn, false);

      if (res.ok) {
        // El servidor devuelve un token nuevo (el anterior ya no sirve porque cambió la contraseña).
        if (res.data.access_token) localStorage.setItem(TOKEN_KEY, res.data.access_token);
        form.reset();
        $("#meter").dataset.level = "0";
        $("#meter-bar").style.width = "0";
        $("#meter-label").textContent = "";
        document.querySelectorAll("#rules li").forEach((li) => li.classList.remove("ok"));
        showAlert("success", res.data.message);
      } else if (res.status === 401) {
        localStorage.removeItem(TOKEN_KEY);
        window.location.replace(LOGIN_URL);
      } else if (res.status === 0) {
        showAlert("error", NETWORK_ERROR);
      } else {
        if (res.status === 400) markInvalid(currentInput, true);
        showAlert("error", extractError(res.data, "No pudimos cambiar la contraseña. Inténtalo de nuevo."));
      }
    });
  }

  // ----------------------------------------------------------------- arranque
  document.addEventListener("DOMContentLoaded", () => {
    const page = document.body.dataset.page;
    if (page === "forgot") initForgot();
    else if (page === "reset") initReset();
    else if (page === "change") initChange();
  });
})();