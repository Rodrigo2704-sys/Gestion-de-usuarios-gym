/* Vista del cliente: estado de su membresía e historial.
   Depende de api-base.js (obtenerToken, cerrarSesion) y api-planes.js (apiVerMembresia, apiObtenerPlanesActivos). */
(() => {
    "use strict";

    const LOGIN_URL = "login.html";
    const CLAVE_NOMBRE = "nombre_usuario";
    const $ = (id) => document.getElementById(id);

    // ---------------------------------------------------------------- utilidades
    function leerToken() {
        return typeof obtenerToken === "function" ? obtenerToken() : localStorage.getItem("token");
    }

    function salir() {
        if (typeof cerrarSesion === "function") { cerrarSesion(); return; }
        localStorage.clear();
        window.location.replace(LOGIN_URL);
    }

    function esErrorDeSesion(error) {
        if (!error) return false;
        if (error.status === 401) return true;
        return /\b401\b|unauthorized|no autenticado|token (inv[aá]lido|expirado)/i.test(String(error.message || ""));
    }

    function mostrarError(texto) {
        const el = $("mensaje");
        el.textContent = texto;   // textContent: nunca interpreta HTML
        el.hidden = false;
    }

    /** "2026-10-08" se lee como fecha local (sin correrse un día por la zona horaria). */
    function parseFecha(valor) {
        if (!valor) return null;
        const texto = String(valor);
        const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(texto);
        const fecha = m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : new Date(texto);
        return Number.isNaN(fecha.getTime()) ? null : fecha;
    }

    function formatearFecha(valor) {
        const f = parseFecha(valor);
        if (!f) return valor ? String(valor) : "N/A";
        return f.toLocaleDateString("es-CO", { year: "numeric", month: "short", day: "numeric" });
    }

    function diasRestantes(valorFin) {
        const fin = parseFecha(valorFin);
        if (!fin) return null;
        const hoy = new Date();
        const inicioHoy = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());
        const inicioFin = new Date(fin.getFullYear(), fin.getMonth(), fin.getDate());
        return Math.round((inicioFin - inicioHoy) / 86400000);
    }

    function celda(texto) {
        const td = document.createElement("td");
        td.textContent = texto == null ? "" : String(texto);
        return td;
    }

    function esActiva(m) {
        return String(m.estado || "").toLowerCase() === "activa";
    }

    // --------------------------------------------------------------------- datos
    async function cargarNombresDePlanes() {
        const nombres = {};
        try {
            const planes = await apiObtenerPlanesActivos();
            if (Array.isArray(planes)) for (const p of planes) nombres[p.id] = p.tipo;
        } catch (error) {
            if (esErrorDeSesion(error)) salir();
            // Si no se pueden traer los nombres, se muestra "Plan #id" y la página sigue funcionando.
        }
        return nombres;
    }

    function pintarResumen(actual, nombres) {
        const resumen = $("resumen");
        const vacio = $("res-vacio");

        if (!actual) {
            resumen.hidden = true;
            vacio.hidden = false;
            vacio.textContent = "No tienes una membresía activa en este momento. Comunícate con el gimnasio para activarla.";
            return;
        }

        vacio.hidden = true;
        resumen.hidden = false;
        $("res-estado").textContent = "Activa";
        $("res-plan").textContent = nombres[actual.plan_id] || ("Plan #" + actual.plan_id);
        $("res-fechas").textContent = "Del " + formatearFecha(actual.fecha_inicio) + " al " + formatearFecha(actual.fecha_fin);

        const dias = diasRestantes(actual.fecha_fin);
        const elDias = $("res-dias");
        elDias.className = "detalle";
        if (dias === null) {
            elDias.textContent = "";
        } else if (dias > 1) {
            elDias.textContent = "Te quedan " + dias + " días.";
        } else if (dias === 1) {
            elDias.textContent = "Te queda 1 día.";
        } else if (dias === 0) {
            elDias.textContent = "Tu membresía vence hoy.";
            elDias.className = "aviso";
        } else {
            elDias.textContent = "La fecha de vencimiento ya pasó. Comunícate con el gimnasio para renovarla.";
            elDias.className = "aviso";
        }
    }

    function pintarHistorial(lista, nombres) {
        const tabla = $("tabla-historial");
        tabla.replaceChildren();

        if (lista.length === 0) {
            const tr = document.createElement("tr");
            const td = document.createElement("td");
            td.colSpan = 4;
            td.className = "vacio";
            td.textContent = "No tienes membresías registradas.";
            tr.appendChild(td);
            tabla.appendChild(tr);
            return;
        }

        for (const m of lista) {
            const estado = String(m.estado || "");
            const tdEstado = document.createElement("td");
            const span = document.createElement("span");
            span.className = esActiva(m) ? "estado-activo" : "estado-otro";
            span.textContent = estado || "N/A";
            tdEstado.appendChild(span);

            const tr = document.createElement("tr");
            tr.append(
                celda(nombres[m.plan_id] || ("Plan #" + m.plan_id)),
                tdEstado,
                celda(formatearFecha(m.fecha_inicio)),
                celda(formatearFecha(m.fecha_fin))
            );
            tabla.appendChild(tr);
        }
    }

    // ---------------------------------------------------------------- arranque
    document.addEventListener("DOMContentLoaded", async () => {
        if (!leerToken()) {
            window.location.replace(LOGIN_URL);
            return;
        }

        const nombre = localStorage.getItem(CLAVE_NOMBRE);
        $("nombre-bienvenida").textContent = nombre || "";
        $("btn-logout").addEventListener("click", salir);

        try {
            const [membresias, nombres] = await Promise.all([apiVerMembresia(), cargarNombresDePlanes()]);
            const lista = Array.isArray(membresias) ? membresias.slice() : [];

            // Más reciente primero (por fecha de fin).
            lista.sort((a, b) => {
                const fa = parseFecha(a.fecha_fin), fb = parseFecha(b.fecha_fin);
                return (fb ? fb.getTime() : -Infinity) - (fa ? fa.getTime() : -Infinity);
            });

            pintarResumen(lista.find(esActiva) || null, nombres);
            pintarHistorial(lista, nombres);
        } catch (error) {
            if (esErrorDeSesion(error)) { salir(); return; }
            $("res-vacio").textContent = "No se pudo cargar tu membresía.";
            mostrarError("No se pudo cargar tu membresía: " + ((error && error.message) || "inténtalo de nuevo."));
        }
    });
})();