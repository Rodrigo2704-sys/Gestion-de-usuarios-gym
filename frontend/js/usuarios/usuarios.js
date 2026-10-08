/* Vista de administración de usuarios.
   Depende de api-usuarios.js: apiListarUsuarios, apiObtenerUsuarioPorId, apiModificarUsuario,
   apiObtenerUsuarioPorCorreo, apiBorrarUsuario, apiCambiarRol. Y de api-base.js (obtenerToken, cerrarSesion).

   Los nombres que llama tu HTML con onclick="..." se dejan globales al final del archivo
   (window.xxx = xxx). Todo lo demás queda privado dentro de esta función. */
(() => {
    "use strict";

    // ------------------------------------------------------------ configuración
    const LOGIN_URL = "login.html";
    const CLIENTE_URL = "cliente.html";      // vista de los clientes (no admins)
    const CLAVE_TOKEN = "token";
    const CLAVE_ROL = "rol";
    const CLAVE_NOMBRE = "nombre_usuario";
    const ROL_ADMIN = 1;
    const ROL_CLIENTE = 2;
    const TAMANO_PAGINA = 20;                // el backend permite hasta 100
    const MAX_CORREO = 150;                  // largo de la columna usuarios.correo
    const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    const $ = (id) => document.getElementById(id);
    let ocupado = false;                     // evita clics dobles mientras hay una operación en curso
    let paginaActual = 0;
    let usuarioEnEdicion = null;             // el usuario cargado en el formulario de edición
    let recargarVista = () => mostrarTablaDeUsuarios(0);   // repite la última vista (lista o búsqueda)

    // ---------------------------------------------------------------- utilidades
    function mostrarMensaje(tipo, texto) {
        let el = $("mensaje");
        if (!el) {   // si tu HTML no tiene el contenedor, lo creamos arriba de la página
            el = document.createElement("div");
            el.id = "mensaje";
            el.setAttribute("role", "status");
            el.style.cssText = "margin:0 0 15px;padding:12px 16px;border-radius:6px;font-size:.95rem;";
            document.body.insertBefore(el, document.body.firstChild);
        }
        el.className = "mensaje " + tipo;    // los estilos .mensaje.ok / .mensaje.error vienen del HTML
        el.style.display = "block";
        el.style.background = tipo === "ok" ? "#e7f5ec" : "#fdecea";
        el.style.color = tipo === "ok" ? "#1b6e3c" : "#b3261e";
        el.textContent = texto;              // textContent: nunca interpreta HTML
    }

    function limpiarMensaje() {
        const el = $("mensaje");
        if (el) { el.style.display = "none"; el.textContent = ""; el.className = "mensaje"; }
    }

    function leerToken() {
        return typeof obtenerToken === "function" ? obtenerToken() : localStorage.getItem(CLAVE_TOKEN);
    }

    function salir() {
        if (typeof cerrarSesion === "function") { cerrarSesion(); return; }
        localStorage.clear();
        window.location.replace(LOGIN_URL);
    }

    function esErrorDeSesion(error) {
        if (!error) return false;
        if (error.estado === 401 || error.status === 401) return true;
        return /\b401\b|unauthorized|no autenticado|token (inv[aá]lido|expirado)/i.test(String(error.message || ""));
    }

    function manejarError(error, prefijo) {
        if (esErrorDeSesion(error)) { salir(); return; }
        mostrarMensaje("error", prefijo + (error && error.message ? error.message : "Inténtalo de nuevo."));
    }

    function esAdmin() {
        return String(localStorage.getItem(CLAVE_ROL) || "").trim().toLowerCase().startsWith("admin");
    }

    /** Ejecuta una acción una sola vez a la vez. */
    async function exclusivo(accion) {
        if (ocupado) return;
        ocupado = true;
        try { await accion(); } finally { ocupado = false; }
    }

    function celda(texto) {
        const td = document.createElement("td");
        td.textContent = texto == null ? "" : String(texto);
        return td;
    }

    function boton(texto, alClic, clase) {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = texto;
        if (clase) b.className = clase;
        b.addEventListener("click", alClic);
        return b;
    }

    function filaVacia(texto) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 6;                      // la tabla tiene 6 columnas
        td.style.textAlign = "center";
        td.textContent = texto;
        tr.appendChild(td);
        return tr;
    }

    function selectorRol(u) {
        const select = document.createElement("select");
        for (const [valor, texto] of [[ROL_ADMIN, "Administrador"], [ROL_CLIENTE, "Cliente"]]) {
            const opcion = document.createElement("option");
            opcion.value = String(valor);
            opcion.textContent = texto;
            select.appendChild(opcion);
        }
        select.value = String(u.rol_id);
        select.addEventListener("change", () => cambiarRolUsuario(u, select));
        return select;
    }

    function celdaEstado(u) {
        const td = document.createElement("td");

        const estado = document.createElement("span");
        estado.className = u.activo ? "badge activo" : "badge inactivo";
        estado.textContent = u.activo ? "Activo" : "Inactivo";
        td.appendChild(estado);

        if (!u.verificado) {
            const pendiente = document.createElement("span");
            pendiente.className = "badge pendiente";
            pendiente.textContent = "Sin verificar";
            td.appendChild(pendiente);
        }
        return td;
    }

    function filaUsuario(u) {
        const tr = document.createElement("tr");

        const celdaRol = document.createElement("td");
        celdaRol.appendChild(selectorRol(u));

        const acciones = document.createElement("td");
        // Sin onclick="..." escrito en HTML: los botones se crean y se enlazan desde JS.
        acciones.append(
            boton("Editar", () => prepararEdicionYBuscarPorId(Number(u.id)), "btn-buscar"),
            u.activo
                ? boton("Desactivar", () => desactivarUsuario(u), "btn-logout")
                : boton("Reactivar", () => reactivarUsuario(u), "btn-guardar")
        );

        tr.append(celda(u.id), celda(u.nombre), celda(u.correo), celdaRol, celdaEstado(u), acciones);
        return tr;
    }

    function pintarUsuarios(lista) {
        const tabla = $("cuerpo-tabla-usuarios");
        if (!tabla) return;
        tabla.replaceChildren();
        if (!Array.isArray(lista) || lista.length === 0) {
            tabla.appendChild(filaVacia("No hay usuarios para mostrar."));
            return;
        }
        for (const u of lista) tabla.appendChild(filaUsuario(u));
    }

    function actualizarPaginacion(anteriorActivo, siguienteActivo, texto) {
        const anterior = $("btn-anterior"), siguiente = $("btn-siguiente"), info = $("info-pagina");
        if (anterior) anterior.disabled = !anteriorActivo;
        if (siguiente) siguiente.disabled = !siguienteActivo;
        if (info) info.textContent = texto;
    }

    // ---------------------------------------------------------------- listar (API 3)
    async function mostrarTablaDeUsuarios(pagina = 0) {
        // Number(...) || 0: si el navegador pasa un evento por error, se usa la página 0.
        paginaActual = Math.max(0, Number(pagina) || 0);
        recargarVista = () => mostrarTablaDeUsuarios(paginaActual);

        try {
            const lista = await apiListarUsuarios(paginaActual * TAMANO_PAGINA, TAMANO_PAGINA);

            // Si la página quedó vacía (era la última), se retrocede una.
            if (Array.isArray(lista) && lista.length === 0 && paginaActual > 0) {
                return mostrarTablaDeUsuarios(paginaActual - 1);
            }

            pintarUsuarios(lista);
            actualizarPaginacion(paginaActual > 0, Array.isArray(lista) && lista.length === TAMANO_PAGINA, "Página " + (paginaActual + 1));
        } catch (error) {
            const tabla = $("cuerpo-tabla-usuarios");
            if (tabla) tabla.replaceChildren(filaVacia("No se pudo cargar la lista."));
            actualizarPaginacion(false, false, "");
            manejarError(error, "Error al cargar la lista: ");
        }
    }

    function mostrarTodos() {
        const campo = $("input-busqueda-correo");
        if (campo) campo.value = "";
        limpiarMensaje();
        return mostrarTablaDeUsuarios(0);
    }

    function paginaAnterior() { return mostrarTablaDeUsuarios(paginaActual - 1); }
    function paginaSiguiente() { return mostrarTablaDeUsuarios(paginaActual + 1); }

    // ---------------------------------------------------- buscar por ID para editar (API 4)
    async function prepararEdicionYBuscarPorId(usuarioId) {
        if (!Number.isInteger(usuarioId) || usuarioId < 1) return;
        limpiarMensaje();
        try {
            const u = await apiObtenerUsuarioPorId(usuarioId);
            const inputId = $("edit-id");
            const inputNombre = $("edit-nombre");
            const inputCorreo = $("edit-correo");
            if (!inputNombre || !inputCorreo) return;

            usuarioEnEdicion = u;
            if (inputId) inputId.value = u.id;
            inputNombre.value = u.nombre || "";
            inputCorreo.value = u.correo || "";
            mostrarMensaje("ok", "Editando al usuario ID " + u.id + ". Cambia los datos y pulsa Guardar Cambios.");
            inputNombre.focus();
        } catch (error) {
            manejarError(error, "No se pudo obtener el usuario: ");
        }
    }

    function cancelarEdicion() {
        usuarioEnEdicion = null;
        for (const id of ["edit-id", "edit-nombre", "edit-correo"]) {
            const campo = $(id);
            if (campo) campo.value = "";
        }
        limpiarMensaje();
    }

    // ---------------------------------------------------------- guardar cambios (API 5)
    async function ejecutarModificacionUsuario() {
        limpiarMensaje();
        const usuarioId = Number(($("edit-id") || {}).value);
        const nombre = $("edit-nombre").value.trim();
        const correo = $("edit-correo").value.trim().toLowerCase();

        if (!Number.isInteger(usuarioId) || usuarioId < 1) {
            mostrarMensaje("error", "Primero elige un usuario con el botón Editar.");
            return;
        }
        if (nombre.length < 2 || nombre.length > 100) {
            mostrarMensaje("error", "El nombre debe tener entre 2 y 100 caracteres.");
            return;
        }
        if (correo.length > MAX_CORREO || !EMAIL_RE.test(correo)) {
            mostrarMensaje("error", "Escribe un correo válido (máximo " + MAX_CORREO + " caracteres).");
            return;
        }

        // PATCH: se envían solo los campos que de verdad cambiaron.
        const original = usuarioEnEdicion && Number(usuarioEnEdicion.id) === usuarioId ? usuarioEnEdicion : null;
        const cambios = {};
        if (!original || nombre !== original.nombre) cambios.nombre = nombre;
        if (!original || correo !== String(original.correo).toLowerCase()) cambios.correo = correo;

        if (Object.keys(cambios).length === 0) {
            mostrarMensaje("error", "No hay cambios para guardar.");
            return;
        }
        if (!confirm("¿Confirmar cambios de edición?")) return;

        await exclusivo(async () => {
            try {
                await apiModificarUsuario(usuarioId, cambios);
                cancelarEdicion();
                await recargarVista();
                mostrarMensaje("ok", "Usuario actualizado correctamente.");
            } catch (error) {
                manejarError(error, "No se pudo actualizar: ");
            }
        });
    }

    // ----------------------------------------------------------- buscar por correo (API 6)
    async function ejecutarBusqueda(correo) {
        recargarVista = () => ejecutarBusqueda(correo);
        try {
            const resultado = await apiObtenerUsuarioPorCorreo(correo);
            const lista = Array.isArray(resultado) ? resultado : (resultado ? [resultado] : []);
            pintarUsuarios(lista);
            actualizarPaginacion(false, false, "Resultado de la búsqueda");
            if (lista.length === 0) mostrarMensaje("error", "No se encontró ningún usuario con ese correo.");
        } catch (error) {
            const tabla = $("cuerpo-tabla-usuarios");
            if (tabla) tabla.replaceChildren(filaVacia("Sin resultados."));
            actualizarPaginacion(false, false, "");
            manejarError(error, "Búsqueda fallida: ");
        }
    }

    async function buscarClienteEspecificoPorCorreo() {
        limpiarMensaje();
        const correo = ($("input-busqueda-correo").value || "").trim().toLowerCase();

        // Búsqueda vacía = volver a mostrar a todos.
        if (!correo) {
            await mostrarTablaDeUsuarios(0);
            return;
        }
        if (correo.length > MAX_CORREO || !EMAIL_RE.test(correo)) {
            mostrarMensaje("error", "Escribe un correo válido para buscar.");
            return;
        }

        await exclusivo(() => ejecutarBusqueda(correo));
    }

    // ------------------------------------------------------------------ cambiar rol (nuevo)
    async function cambiarRolUsuario(u, select) {
        const nuevoRol = Number(select.value);
        const rolAnterior = u.rol_id;
        if (nuevoRol === rolAnterior) return;

        // Si hay otra operación en curso, o la persona se arrepiente, el selector vuelve atrás.
        if (ocupado) { select.value = String(rolAnterior); return; }
        if (nuevoRol === ROL_ADMIN && !confirm("¿Dar permisos de Administrador a " + u.nombre + "?")) {
            select.value = String(rolAnterior);
            return;
        }

        limpiarMensaje();
        await exclusivo(async () => {
            select.disabled = true;
            try {
                await apiCambiarRol(Number(u.id), nuevoRol);
                u.rol_id = nuevoRol;
                mostrarMensaje("ok", "Rol de " + u.nombre + " actualizado correctamente.");
            } catch (error) {
                select.value = String(rolAnterior);   // por ejemplo: "No puedes cambiar tu propio rol"
                manejarError(error, "No se pudo cambiar el rol: ");
            } finally {
                select.disabled = false;
            }
        });
    }

    // ------------------------------------------- desactivar y reactivar (API 7: borrado lógico)
    async function desactivarUsuario(u) {
        limpiarMensaje();
        if (!confirm("¿Desactivar a " + u.nombre + "? No podrá iniciar sesión, pero su historial se conserva.")) return;

        await exclusivo(async () => {
            try {
                const respuesta = await apiBorrarUsuario(Number(u.id));
                await recargarVista();
                const texto = respuesta && (respuesta.mensaje || respuesta.Mensaje);
                mostrarMensaje("ok", texto ? String(texto) : "Usuario desactivado.");
            } catch (error) {
                manejarError(error, "No se pudo desactivar: ");   // por ejemplo: "No puedes eliminar tu propia cuenta"
            }
        });
    }

    async function reactivarUsuario(u) {
        limpiarMensaje();
        await exclusivo(async () => {
            try {
                await apiModificarUsuario(Number(u.id), { activo: true });
                await recargarVista();
                mostrarMensaje("ok", u.nombre + " fue reactivado.");
            } catch (error) {
                manejarError(error, "No se pudo reactivar: ");
            }
        });
    }

    // Se dejan globales las funciones que tu HTML llama con onclick="...".
    // (Antes faltaba mostrarTablaDeUsuarios: por eso "Mostrar Todos" daba error.)
    window.mostrarTablaDeUsuarios = mostrarTablaDeUsuarios;
    window.mostrarTodos = mostrarTodos;
    window.paginaAnterior = paginaAnterior;
    window.paginaSiguiente = paginaSiguiente;
    window.buscarClienteEspecificoPorCorreo = buscarClienteEspecificoPorCorreo;
    window.ejecutarModificacionUsuario = ejecutarModificacionUsuario;
    window.cancelarEdicion = cancelarEdicion;

    // ---------------------------------------------------------------- arranque
    document.addEventListener("DOMContentLoaded", async () => {
        if (!leerToken()) {
            window.location.replace(LOGIN_URL);
            return;
        }

        // Barrera visual: un cliente no ve esta pantalla. La seguridad real la aplica el servidor
        // en cada endpoint. Si la sesión es antigua y no guardó el rol, se deja pasar y el servidor decide.
        if (localStorage.getItem(CLAVE_ROL) && !esAdmin()) {
            window.location.replace(CLIENTE_URL);
            return;
        }

        const nombre = localStorage.getItem(CLAVE_NOMBRE);
        const saludo = $("nombre-bienvenida");
        if (saludo && nombre) saludo.textContent = nombre;

        await mostrarTablaDeUsuarios(0);
    });
})();