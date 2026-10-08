/* Vista de planes y membresías.
   Depende de api-base.js (obtenerToken, cerrarSesion) y api-planes.js
   (apiCreacionPlan, apiObtenerPlanesActivos, apiAsignarMembresia, apiVerMembresia). */
(() => {
    "use strict";

    // ------------------------------------------------------------ configuración
    const LOGIN_URL = "login.html";
    const CLAVE_NOMBRE = "nombre_usuario";   // donde tu login guarda el nombre
    const CLAVE_ROL = "rol";                 // misma clave que guarda apiIniciarSesion (api-usuarios.js)
    const ROLES_ADMIN = ["admin", "administrador"];

    const $ = (id) => document.getElementById(id);
    const formatoPrecio = new Intl.NumberFormat("es-CO", {
        style: "currency", currency: "COP", minimumFractionDigits: 0, maximumFractionDigits: 2,
    });

    // ---------------------------------------------------------------- utilidades
    function mostrarMensaje(tipo, texto) {
        const el = $("mensaje");
        if (!el) return;
        el.className = "mensaje " + tipo;
        el.textContent = texto;   // textContent: nunca interpreta HTML
        el.hidden = false;
    }

    function limpiarMensaje() {
        const el = $("mensaje");
        if (el) { el.hidden = true; el.textContent = ""; }
    }

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

    /** Si la sesión venció, saca al usuario; si no, muestra el error. */
    function manejarError(error, prefijo) {
        if (esErrorDeSesion(error)) {
            salir();
            return;
        }
        mostrarMensaje("error", prefijo + (error && error.message ? error.message : "Inténtalo de nuevo."));
    }

    function esAdmin() {
        const rol = String(localStorage.getItem(CLAVE_ROL) || "").trim().toLowerCase();
        return ROLES_ADMIN.includes(rol);
    }

    function formatearFecha(valor) {
        if (!valor) return "N/A";
        const texto = String(valor);
        const soloFecha = /^(\d{4})-(\d{2})-(\d{2})$/.exec(texto);
        // Una fecha "2026-10-08" se arma como fecha local para que no se corra un día por la zona horaria.
        const fecha = soloFecha
            ? new Date(Number(soloFecha[1]), Number(soloFecha[2]) - 1, Number(soloFecha[3]))
            : new Date(texto);
        if (Number.isNaN(fecha.getTime())) return texto;
        return fecha.toLocaleDateString("es-CO", { year: "numeric", month: "short", day: "numeric" });
    }

    function celda(texto) {
        const td = document.createElement("td");
        td.textContent = texto == null ? "" : String(texto);
        return td;
    }

    function filaVacia(columnas, texto) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = columnas;
        td.className = "vacio";
        td.textContent = texto;
        tr.appendChild(td);
        return tr;
    }

    /** Desactiva el botón mientras corre la acción, para evitar clics dobles (planes o asignaciones duplicadas). */
    async function conBoton(boton, textoOcupado, accion) {
        if (boton.disabled) return;
        const original = boton.textContent;
        boton.disabled = true;
        boton.textContent = textoOcupado;
        try {
            await accion();
        } finally {
            boton.disabled = false;
            boton.textContent = original;
        }
    }

    // ---------------------------------------------------------------- 1. crear plan
    async function crearNuevoPlan() {
        limpiarMensaje();
        const nombre = $("crear-nombre").value.trim();
        const precio = Number($("crear-precio").value);
        const duracion_dias = Number($("crear-duracion").value);

        if (nombre.length < 2 || nombre.length > 100) {
            mostrarMensaje("error", "El nombre del plan debe tener entre 2 y 100 caracteres.");
            return;
        }
        if (!Number.isFinite(precio) || precio <= 0 || precio > 99999999.99) {
            mostrarMensaje("error", "El precio debe ser un número mayor que 0.");
            return;
        }
        if (!Number.isInteger(duracion_dias) || duracion_dias < 1 || duracion_dias > 3650) {
            mostrarMensaje("error", "La duración debe ser un número entero de días entre 1 y 3650.");
            return;
        }

        try {
            // El backend espera exactamente: tipo, precio y duracion (rechaza campos extra).
            await apiCreacionPlan({ tipo: nombre, precio, duracion: duracion_dias });
            $("crear-nombre").value = "";
            $("crear-precio").value = "";
            $("crear-duracion").value = "";
            mostrarMensaje("ok", "Plan creado correctamente.");
            await cargarPlanesEnPantalla();
        } catch (error) {
            manejarError(error, "No se pudo crear el plan: ");
        }
    }

    // ---------------------------------------------- 2 y 3. listar planes, tabla y select
    async function cargarPlanesEnPantalla() {
        const tabla = $("tabla-planes-activos");
        const select = $("asignar-plan-select");

        try {
            const planes = await apiObtenerPlanesActivos();
            const lista = Array.isArray(planes) ? planes : [];

            tabla.replaceChildren();
            select.replaceChildren(new Option("Seleccione un plan...", ""));

            if (lista.length === 0) {
                tabla.appendChild(filaVacia(4, "Todavía no hay planes activos."));
                return;
            }

            for (const p of lista) {
                const precio = formatoPrecio.format(Number(p.precio));
                const tr = document.createElement("tr");
                tr.append(celda(p.id), celda(p.tipo), celda(precio), celda(p.duracion + " días"));
                tabla.appendChild(tr);

                // new Option(texto, valor) asigna texto plano: no interpreta HTML.
                select.appendChild(new Option(p.tipo + " (" + precio + ")", String(p.id)));
            }
        } catch (error) {
            tabla.replaceChildren(filaVacia(4, "No se pudieron cargar los planes."));
            if (esErrorDeSesion(error)) salir();
            else console.error("No se pudieron cargar los planes:", error);
        }
    }

    // ---------------------------------------------------------------- asignar membresía
    async function asignarMembresiaUsuario() {
        limpiarMensaje();
        const usuario_id = Number($("asignar-usuario-id").value);
        const plan_id = Number($("asignar-plan-select").value);

        if (!Number.isInteger(usuario_id) || usuario_id < 1) {
            mostrarMensaje("error", "Ingresa un ID de usuario válido (número entero mayor que 0).");
            return;
        }
        if (!Number.isInteger(plan_id) || plan_id < 1) {
            mostrarMensaje("error", "Selecciona un plan.");
            return;
        }

        try {
            await apiAsignarMembresia({ usuario_id, plan_id });
            $("asignar-usuario-id").value = "";
            mostrarMensaje("ok", "Membresía asignada al usuario " + usuario_id + ".");
        } catch (error) {
            manejarError(error, "No se pudo asignar la membresía: ");
        }
    }

    // ---------------------------------------------------------------- mis membresías
    async function cargarMiMembresiaPersonal() {
        const tabla = $("tabla-mi-membresia");
        try {
            const membresias = await apiVerMembresia();
            tabla.replaceChildren();

            if (!Array.isArray(membresias) || membresias.length === 0) {
                tabla.appendChild(filaVacia(5, "No tienes membresías registradas."));
                return;
            }

            for (const m of membresias) {
                const estado = String(m.estado || "");
                const tdEstado = document.createElement("td");
                const badge = document.createElement("span");
                badge.className = estado.toLowerCase() === "activa" ? "estado-activo" : "estado-otro";
                badge.textContent = estado || "N/A";
                tdEstado.appendChild(badge);

                const tr = document.createElement("tr");
                tr.append(
                    celda(m.id),
                    celda(m.plan_id),
                    tdEstado,
                    celda(formatearFecha(m.fecha_inicio)),
                    celda(formatearFecha(m.fecha_fin))
                );
                tabla.appendChild(tr);
            }
        } catch (error) {
            tabla.replaceChildren(filaVacia(5, "No se pudo cargar tu historial."));
            if (esErrorDeSesion(error)) salir();
            else console.error("Error al cargar historial de membresías:", error);
        }
    }

    // ---------------------------------------------------------------- arranque
    document.addEventListener("DOMContentLoaded", async () => {
        if (!leerToken()) {
            window.location.replace(LOGIN_URL);
            return;
        }

        const nombre = localStorage.getItem(CLAVE_NOMBRE);
        if (nombre) $("nombre-bienvenida").textContent = nombre;

        $("btn-logout").addEventListener("click", salir);

        // Los formularios de administración solo se muestran a admins (control visual; el servidor es quien manda).
        const admin = esAdmin();
        $("seccion-crear-plan").hidden = !admin;
        $("seccion-asignar").hidden = !admin;
        const enlaceUsuarios = $("enlace-usuarios");
        if (enlaceUsuarios) enlaceUsuarios.hidden = !admin;

        if (admin) {
            const btnCrear = $("btn-crear-plan");
            const btnAsignar = $("btn-asignar");
            btnCrear.addEventListener("click", () => conBoton(btnCrear, "Guardando…", crearNuevoPlan));
            btnAsignar.addEventListener("click", () => conBoton(btnAsignar, "Asignando…", asignarMembresiaUsuario));
        }

        await Promise.all([cargarPlanesEnPantalla(), cargarMiMembresiaPersonal()]);
    });
})();