// js/registro.js
// Requiere (en este orden): api-base.js, api-usuarios.js, auth-ui.js
(() => {
    "use strict";

    const PAGINA_VERIFICAR = "verificar.html";
    const $ = (id) => document.getElementById(id);

    document.addEventListener("DOMContentLoaded", () => {
        AuthUI.enlazarMostrarPassword();
        AuthUI.enlazarMedidor($("password"));

        const form = $("registro-form");
        const btn = $("btn-registrar");

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            AuthUI.limpiarAlerta();

            const nombre = $("nombre").value.trim();
            const correo = $("correo").value.trim().toLowerCase();
            const password = $("password").value;
            const repetida = $("confirm_password").value;

            // El servidor vuelve a validar todo; esto solo evita peticiones inútiles.
            if (nombre.length < 2 || nombre.length > 100) {
                AuthUI.marcarInvalido($("nombre"), true);
                AuthUI.mostrarAlerta("error", "El nombre debe tener entre 2 y 100 caracteres.");
                return;
            }
            AuthUI.marcarInvalido($("nombre"), false);

            if (!AuthUI.correoValido(correo)) {
                AuthUI.marcarInvalido($("correo"), true);
                AuthUI.mostrarAlerta("error", "Escribe un correo válido.");
                return;
            }
            AuthUI.marcarInvalido($("correo"), false);

            const problema = AuthUI.validarPassword(password, repetida);
            AuthUI.marcarInvalido($("password"), !!problema);
            AuthUI.marcarInvalido($("confirm_password"), !!problema);
            if (problema) {
                AuthUI.mostrarAlerta("error", problema);
                return;
            }

            AuthUI.ocupado(btn, true, "Creando cuenta…");
            try {
                // El backend rechaza campos extra: solo se envían nombre, correo y password.
                await apiRegistrarUsuario({ nombre, correo, password });
                AuthUI.guardarCorreoPendiente(correo);
                AuthUI.marcarCodigoEnviado();
                window.location.href = PAGINA_VERIFICAR;
            } catch (error) {
                AuthUI.mostrarAlerta("error", error.message);
                AuthUI.ocupado(btn, false);
            }
        });
    });
})();
