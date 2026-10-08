// js/login.js
// Requiere (en este orden): api-base.js, api-usuarios.js, auth-ui.js
(() => {
    "use strict";

    const PAGINA_ADMIN = "usuarios.html";      // panel de administración
    const PAGINA_CLIENTE = "cliente.html";     // vista de los clientes
    const PAGINA_VERIFICAR = "verificar.html"; // pantalla para escribir el código del correo

    const $ = (id) => document.getElementById(id);

    document.addEventListener("DOMContentLoaded", () => {
        AuthUI.enlazarMostrarPassword();

        const form = $("iniciarsesion");
        const btn = $("btn-entrar");

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            AuthUI.limpiarAlerta();

            const correo = $("correo").value.trim().toLowerCase();
            const password = $("password").value;   // la contraseña conserva los espacios exactos

            if (!AuthUI.correoValido(correo) || !password) {
                AuthUI.mostrarAlerta("error", "Escribe tu correo y tu contraseña.");
                return;
            }

            AuthUI.ocupado(btn, true, "Entrando…");
            try {
                // apiIniciarSesion hace el POST y guarda token, nombre y rol en localStorage.
                const data = await apiIniciarSesion(correo, password);
                const esAdmin = String(data.rol).toLowerCase().startsWith("admin");
                window.location.href = esAdmin ? PAGINA_ADMIN : PAGINA_CLIENTE;
            } catch (error) {
                // 403 = la contraseña es correcta pero el correo aún no está verificado.
                if (error.status === 403) {
                    AuthUI.guardarCorreoPendiente(correo);
                    window.location.href = PAGINA_VERIFICAR;
                    return;
                }
                AuthUI.mostrarAlerta("error", error.message);
            } finally {
                AuthUI.ocupado(btn, false);
            }
        });
    });
})();
