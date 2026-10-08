// js/restablecer.js  (paso 2 de "olvidé mi contraseña": código + contraseña nueva)
// Requiere (en este orden): api-base.js, api-usuarios.js, auth-ui.js
(() => {
    "use strict";

    const $ = (id) => document.getElementById(id);

    document.addEventListener("DOMContentLoaded", () => {
        AuthUI.enlazarMostrarPassword();
        AuthUI.enlazarMedidor($("new_password"));

        const correoInput = $("correo");
        const codigoInput = $("codigo");
        const nuevaInput = $("new_password");
        const repetidaInput = $("confirm_password");
        const btn = $("btn-guardar");

        correoInput.value = AuthUI.leerCorreoPendiente();
        if (correoInput.value) codigoInput.focus(); else correoInput.focus();

        codigoInput.addEventListener("input", () => {
            codigoInput.value = codigoInput.value.replace(/\D/g, "").slice(0, 6);
        });

        $("restablecer-form").addEventListener("submit", async (e) => {
            e.preventDefault();
            AuthUI.limpiarAlerta();

            const correo = correoInput.value.trim().toLowerCase();
            const codigo = codigoInput.value.trim();

            if (!AuthUI.correoValido(correo)) {
                AuthUI.marcarInvalido(correoInput, true);
                AuthUI.mostrarAlerta("error", "Escribe el correo de tu cuenta.");
                return;
            }
            AuthUI.marcarInvalido(correoInput, false);

            if (!/^\d{6}$/.test(codigo)) {
                AuthUI.marcarInvalido(codigoInput, true);
                AuthUI.mostrarAlerta("error", "El código tiene 6 dígitos.");
                return;
            }
            AuthUI.marcarInvalido(codigoInput, false);

            const problema = AuthUI.validarPassword(nuevaInput.value, repetidaInput.value);
            AuthUI.marcarInvalido(nuevaInput, !!problema);
            AuthUI.marcarInvalido(repetidaInput, !!problema);
            if (problema) {
                AuthUI.mostrarAlerta("error", problema);
                return;
            }

            AuthUI.ocupado(btn, true, "Guardando…");
            try {
                await apiRestablecerPassword(correo, codigo, nuevaInput.value);
                nuevaInput.value = "";
                repetidaInput.value = "";
                AuthUI.borrarCorreoPendiente();
                $("seccion-form").hidden = true;
                $("seccion-exito").hidden = false;
            } catch (error) {
                AuthUI.mostrarAlerta("error", error.message);
                AuthUI.ocupado(btn, false);
            }
        });
    });
})();
