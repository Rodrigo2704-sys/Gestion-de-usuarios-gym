// js/cambiar-password.js  (usuario con sesión iniciada; pide la contraseña actual)
// Requiere (en este orden): api-base.js, api-usuarios.js, auth-ui.js
(() => {
    "use strict";

    const $ = (id) => document.getElementById(id);

    document.addEventListener("DOMContentLoaded", () => {
        if (!obtenerToken()) {
            window.location.replace(PAGINA_LOGIN);
            return;
        }

        AuthUI.enlazarMostrarPassword();
        AuthUI.enlazarMedidor($("new_password"));

        // El enlace "Volver" depende del rol: admin -> usuarios.html, cliente -> cliente.html
        const rol = String(localStorage.getItem("rol") || "").trim().toLowerCase();
        if (rol.startsWith("admin")) $("volver").href = "usuarios.html";

        const form = $("cambiar-form");
        const actualInput = $("current_password");
        const nuevaInput = $("new_password");
        const repetidaInput = $("confirm_password");
        const btn = $("btn-guardar");

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            AuthUI.limpiarAlerta();

            if (!actualInput.value) {
                AuthUI.marcarInvalido(actualInput, true);
                AuthUI.mostrarAlerta("error", "Escribe tu contraseña actual.");
                return;
            }
            AuthUI.marcarInvalido(actualInput, false);

            const problema = AuthUI.validarPassword(nuevaInput.value, repetidaInput.value);
            AuthUI.marcarInvalido(nuevaInput, !!problema);
            AuthUI.marcarInvalido(repetidaInput, !!problema);
            if (problema) {
                AuthUI.mostrarAlerta("error", problema);
                return;
            }
            if (nuevaInput.value === actualInput.value) {
                AuthUI.mostrarAlerta("error", "La nueva contraseña debe ser diferente a la actual.");
                return;
            }

            AuthUI.ocupado(btn, true, "Guardando…");
            try {
                const data = await apiCambiarPassword(actualInput.value, nuevaInput.value);
                form.reset();
                AuthUI.reiniciarMedidor();
                AuthUI.mostrarAlerta("success", AuthUI.mensajeDe(data, "Contraseña actualizada correctamente."));
            } catch (error) {
                // Un 401 ya cierra la sesión dentro de apiFetch; un 400 es "contraseña actual incorrecta".
                AuthUI.marcarInvalido(actualInput, error.status === 400);
                AuthUI.mostrarAlerta("error", error.message);
            } finally {
                AuthUI.ocupado(btn, false);
            }
        });
    });
})();
