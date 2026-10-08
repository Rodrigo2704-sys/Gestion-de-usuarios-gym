// js/recuperar.js  (paso 1 de "olvidé mi contraseña": pedir el código)
// Requiere (en este orden): api-base.js, api-usuarios.js, auth-ui.js
(() => {
    "use strict";

    const PAGINA_RESTABLECER = "restablecer.html";
    const $ = (id) => document.getElementById(id);

    document.addEventListener("DOMContentLoaded", () => {
        const correoInput = $("correo");
        const btn = $("btn-enviar");

        correoInput.value = AuthUI.leerCorreoPendiente();

        $("recuperar-form").addEventListener("submit", async (e) => {
            e.preventDefault();
            AuthUI.limpiarAlerta();

            const correo = correoInput.value.trim().toLowerCase();
            if (!AuthUI.correoValido(correo)) {
                AuthUI.marcarInvalido(correoInput, true);
                AuthUI.mostrarAlerta("error", "Escribe un correo válido.");
                return;
            }
            AuthUI.marcarInvalido(correoInput, false);

            AuthUI.ocupado(btn, true, "Enviando…");
            try {
                const data = await apiOlvidePassword(correo);
                AuthUI.guardarCorreoPendiente(correo);
                AuthUI.marcarCodigoEnviado();
                // El servidor responde igual exista o no el correo (así no se revela quién está registrado).
                AuthUI.mostrarAlerta("success", AuthUI.mensajeDe(data, "Si el correo está registrado, recibirás un código en unos minutos."));
                setTimeout(() => { window.location.href = PAGINA_RESTABLECER; }, 2500);
            } catch (error) {
                AuthUI.mostrarAlerta("error", error.message);
                AuthUI.ocupado(btn, false);
            }
        });
    });
})();
