// ====================================================================================
// auth-ui.js  (cargar DESPUÉS de api-base.js y ANTES del js de cada pantalla)
// Ayudas compartidas por las pantallas de autenticación: alertas, botón "ocupado",
// mostrar/ocultar contraseña, medidor de seguridad, validaciones y el correo que viaja
// entre pantallas (registro -> verificar, recuperar -> restablecer).
// ====================================================================================
const AuthUI = (() => {
    "use strict";

    const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const MAX_CORREO = 150;          // largo de la columna usuarios.correo
    const MAX_PASSWORD_BYTES = 72;   // límite de bcrypt (igual que el backend)
    const CLAVE_CORREO = "correo_pendiente";
    const CLAVE_ENVIO = "codigo_enviado_en";
    const ESPERA_REENVIO_SEG = 60;   // igual que CODIGO_REENVIO_SEGUNDOS del backend

    const $ = (id) => document.getElementById(id);

    // ------------------------------------------------------------------ alertas
    function mostrarAlerta(tipo, texto) {   // tipo: "error" | "success" | "info"
        const el = $("alert");
        if (!el) return;
        el.className = "alert " + tipo;
        el.textContent = texto;             // textContent: nunca interpreta HTML
        el.hidden = false;
    }

    function limpiarAlerta() {
        const el = $("alert");
        if (el) { el.hidden = true; el.textContent = ""; }
    }

    /** Desactiva el botón y cambia su texto mientras corre la petición (evita clics dobles). */
    function ocupado(boton, activo, textoOcupado) {
        if (!boton) return;
        if (activo) {
            boton.dataset.etiqueta = boton.textContent;
            boton.textContent = textoOcupado;
            boton.disabled = true;
        } else {
            boton.textContent = boton.dataset.etiqueta || boton.textContent;
            boton.disabled = false;
        }
    }

    function marcarInvalido(input, invalido) {
        if (input) input.setAttribute("aria-invalid", invalido ? "true" : "false");
    }

    // -------------------------------------------------------------- validaciones
    function correoValido(correo) {
        return correo.length > 0 && correo.length <= MAX_CORREO && EMAIL_RE.test(correo);
    }

    function reglasPassword(pw) {
        return {
            length: pw.length >= 8,
            letter: /[A-Za-z]/.test(pw),
            number: /\d/.test(pw),
            bytes: new TextEncoder().encode(pw).length <= MAX_PASSWORD_BYTES,
        };
    }

    /** Devuelve un mensaje de error o null si la contraseña nueva es aceptable. */
    function validarPassword(nueva, repetida) {
        const r = reglasPassword(nueva);
        if (!r.length) return "La contraseña debe tener al menos 8 caracteres.";
        if (!r.bytes) return "La contraseña es demasiado larga (máximo 72 bytes).";
        if (!r.letter || !r.number) return "La contraseña debe incluir al menos una letra y un número.";
        if (nueva !== repetida) return "Las contraseñas no coinciden.";
        return null;
    }

    // ----------------------------------------------- mostrar/ocultar y medidor
    function enlazarMostrarPassword() {
        document.querySelectorAll("[data-toggle-password]").forEach((btn) => {
            btn.addEventListener("click", () => {
                const input = $(btn.dataset.togglePassword);
                if (!input) return;
                const mostrar = input.type === "password";
                input.type = mostrar ? "text" : "password";
                btn.textContent = mostrar ? "Ocultar" : "Mostrar";
                btn.setAttribute("aria-label", mostrar ? "Ocultar contraseña" : "Mostrar contraseña");
            });
        });
    }

    function nivelPassword(pw) {
        if (!pw) return 0;
        let puntos = 0;
        if (pw.length >= 8) puntos++;
        if (pw.length >= 12) puntos++;
        if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) puntos++;
        if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) puntos++;
        return Math.max(1, puntos);
    }

    function enlazarMedidor(input) {
        const medidor = $("meter"), barra = $("meter-bar"), etiqueta = $("meter-label");
        const reglas = document.querySelectorAll("#rules li");
        if (!input || !medidor) return;
        const textos = ["", "Débil", "Aceptable", "Buena", "Muy buena"];

        input.addEventListener("input", () => {
            const nivel = nivelPassword(input.value);
            medidor.dataset.level = String(nivel);
            barra.style.width = (nivel * 25) + "%";
            etiqueta.textContent = textos[nivel];
            const r = reglasPassword(input.value);
            reglas.forEach((li) => li.classList.toggle("ok", !!r[li.dataset.rule]));
        });
    }

    function reiniciarMedidor() {
        const medidor = $("meter"), barra = $("meter-bar"), etiqueta = $("meter-label");
        if (medidor) medidor.dataset.level = "0";
        if (barra) barra.style.width = "0";
        if (etiqueta) etiqueta.textContent = "";
        document.querySelectorAll("#rules li").forEach((li) => li.classList.remove("ok"));
    }

    // --------------------------------- datos que viajan entre pantallas (sessionStorage)
    function guardarCorreoPendiente(correo) {
        try { sessionStorage.setItem(CLAVE_CORREO, correo); } catch (_) { /* almacenamiento bloqueado */ }
    }
    function leerCorreoPendiente() {
        try { return sessionStorage.getItem(CLAVE_CORREO) || ""; } catch (_) { return ""; }
    }
    function borrarCorreoPendiente() {
        try { sessionStorage.removeItem(CLAVE_CORREO); sessionStorage.removeItem(CLAVE_ENVIO); } catch (_) { /* nada */ }
    }

    /** Anota que se acaba de pedir un código, para respetar la espera de reenvío del servidor. */
    function marcarCodigoEnviado() {
        try { sessionStorage.setItem(CLAVE_ENVIO, String(Date.now())); } catch (_) { /* nada */ }
    }
    function segundosDeEspera() {
        try {
            const t = Number(sessionStorage.getItem(CLAVE_ENVIO));
            if (!t) return 0;
            return Math.max(0, ESPERA_REENVIO_SEG - Math.floor((Date.now() - t) / 1000));
        } catch (_) { return 0; }
    }

    /** Texto de las respuestas del backend, que usan la clave "Mensaje". */
    function mensajeDe(data, porDefecto) {
        return (data && (data.Mensaje || data.mensaje)) || porDefecto;
    }

    return {
        ESPERA_REENVIO_SEG,
        mostrarAlerta, limpiarAlerta, ocupado, marcarInvalido,
        correoValido, validarPassword,
        enlazarMostrarPassword, enlazarMedidor, reiniciarMedidor,
        guardarCorreoPendiente, leerCorreoPendiente, borrarCorreoPendiente,
        marcarCodigoEnviado, segundosDeEspera, mensajeDe,
    };
})();
