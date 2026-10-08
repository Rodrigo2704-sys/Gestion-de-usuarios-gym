// js/verificar.js
// Requiere (en este orden): api-base.js, api-usuarios.js, auth-ui.js
(() => {
    "use strict";

    const PAGINA_LOGIN = "login.html";
    const $ = (id) => document.getElementById(id);
    let temporizador = null;

    /** Bloquea el botón "Reenviar" y cuenta hacia atrás (el servidor también exige esa espera). */
    function iniciarEspera(segundos) {
        const btn = $("btn-reenviar");
        clearInterval(temporizador);
        let restante = segundos;

        const pintar = () => {
            if (restante > 0) {
                btn.disabled = true;
                btn.textContent = "Reenviar código (" + restante + "s)";
            } else {
                clearInterval(temporizador);
                btn.disabled = false;
                btn.textContent = "Reenviar código";
            }
        };

        pintar();
        if (restante > 0) temporizador = setInterval(() => { restante--; pintar(); }, 1000);
    }

    document.addEventListener("DOMContentLoaded", () => {
        const correoInput = $("correo");
        const codigoInput = $("codigo");
        const btnVerificar = $("btn-verificar");
        const btnReenviar = $("btn-reenviar");

        correoInput.value = AuthUI.leerCorreoPendiente();
        if (correoInput.value) codigoInput.focus(); else correoInput.focus();

        // Si acaba de registrarse (o de pedir otro código), se respeta la espera del servidor.
        iniciarEspera(AuthUI.segundosDeEspera());

        // Solo dígitos, máximo 6.
        codigoInput.addEventListener("input", () => {
            codigoInput.value = codigoInput.value.replace(/\D/g, "").slice(0, 6);
        });

        $("verificar-form").addEventListener("submit", async (e) => {
            e.preventDefault();
            AuthUI.limpiarAlerta();

            const correo = correoInput.value.trim().toLowerCase();
            const codigo = codigoInput.value.trim();

            if (!AuthUI.correoValido(correo)) {
                AuthUI.marcarInvalido(correoInput, true);
                AuthUI.mostrarAlerta("error", "Escribe el correo con el que te registraste.");
                return;
            }
            AuthUI.marcarInvalido(correoInput, false);

            if (!/^\d{6}$/.test(codigo)) {
                AuthUI.marcarInvalido(codigoInput, true);
                AuthUI.mostrarAlerta("error", "El código tiene 6 dígitos.");
                return;
            }
            AuthUI.marcarInvalido(codigoInput, false);

            AuthUI.ocupado(btnVerificar, true, "Verificando…");
            try {
                await apiVerificarCorreo(correo, codigo);
                AuthUI.borrarCorreoPendiente();
                clearInterval(temporizador);
                $("seccion-form").hidden = true;
                $("seccion-exito").hidden = false;
                setTimeout(() => { window.location.href = PAGINA_LOGIN; }, 3000);
            } catch (error) {
                AuthUI.mostrarAlerta("error", error.message);
                AuthUI.ocupado(btnVerificar, false);
            }
        });

        btnReenviar.addEventListener("click", async () => {
            AuthUI.limpiarAlerta();
            const correo = correoInput.value.trim().toLowerCase();
            if (!AuthUI.correoValido(correo)) {
                AuthUI.marcarInvalido(correoInput, true);
                AuthUI.mostrarAlerta("error", "Escribe tu correo para reenviarte el código.");
                return;
            }
            AuthUI.marcarInvalido(correoInput, false);

            btnReenviar.disabled = true;
            btnReenviar.textContent = "Enviando…";
            try {
                const data = await apiReenviarCodigo(correo);
                AuthUI.guardarCorreoPendiente(correo);
                AuthUI.marcarCodigoEnviado();
                AuthUI.mostrarAlerta("info", AuthUI.mensajeDe(data, "Si el correo está registrado, recibirás un código en unos minutos."));
                iniciarEspera(AuthUI.ESPERA_REENVIO_SEG);
            } catch (error) {
                AuthUI.mostrarAlerta("error", error.message);
                iniciarEspera(AuthUI.segundosDeEspera());
            }
        });
    });
})();
