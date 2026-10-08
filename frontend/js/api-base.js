// ====================================================================================
// api-base.js  ->  cargar SIEMPRE ANTES que api-usuarios.js, api-planes.js y los js de pantalla
// Aquí vive lo que comparten todos: la URL, el token y la función que hace el fetch.
// ====================================================================================

const API_BASE_URL = "http://127.0.0.1:8000";
const PAGINA_LOGIN = "login.html";

function obtenerToken() {
    return localStorage.getItem("token");
}

function cerrarSesion() {
    localStorage.removeItem("token");
    localStorage.removeItem("nombre_usuario");
    localStorage.removeItem("rol");
    window.location.href = PAGINA_LOGIN;
}

// Convierte la respuesta de error del backend en un mensaje legible.
function mensajeDeError(data, estado) {
    if (estado === 429) return "Demasiados intentos. Espera un minuto e inténtalo de nuevo.";
    if (estado >= 500) return "Error en el servidor. Inténtalo de nuevo más tarde.";

    const detalle = data && data.detail;
    if (typeof detalle === "string") return detalle;

    // Errores de validación (422): FastAPI manda una lista de objetos, no un texto.
    if (Array.isArray(detalle)) {
        return detalle.map(d => String(d.msg).replace(/^Value error, /, "")).join(". ");
    }
    return "No se pudo completar la operación.";
}

// Error con el código HTTP adjunto (error.status). Lo usan login.js (403 = correo sin verificar)
// y las pantallas que detectan sesión vencida (401). Estado 0 = no hubo conexión.
function crearError(mensaje, estado) {
    const error = new Error(mensaje);
    error.status = estado;
    return error;
}

/**
 * Hace la petición a la API.
 *  - metodo:       "GET", "POST", "PUT", "PATCH" o "DELETE"
 *  - cuerpo:       objeto a enviar como JSON (o URLSearchParams si formulario = true)
 *  - autenticado:  false solo para rutas públicas (login, registro, verificación, recuperación)
 */
async function apiFetch(ruta, { metodo = "GET", cuerpo = null, autenticado = true, formulario = false } = {}) {
    const headers = {};

    if (autenticado) {
        const token = obtenerToken();
        if (!token) {
            cerrarSesion();
            throw crearError("Sesión no iniciada.", 401);
        }
        headers["Authorization"] = `Bearer ${token}`;
    }

    let body;
    if (cuerpo !== null) {
        if (formulario) {
            body = cuerpo; // URLSearchParams (el login de FastAPI no acepta JSON)
            headers["Content-Type"] = "application/x-www-form-urlencoded";
        } else {
            body = JSON.stringify(cuerpo);
            headers["Content-Type"] = "application/json";
        }
    }

    let respuesta;
    try {
        respuesta = await fetch(`${API_BASE_URL}${ruta}`, { method: metodo, headers, body });
    } catch (error) {
        throw crearError("No se pudo conectar con el servidor.", 0);
    }

    // Si el cuerpo viene vacío o no es JSON, no queremos que reviente aquí.
    let data = null;
    try {
        data = await respuesta.json();
    } catch (error) { /* sin cuerpo JSON */ }

    if (!respuesta.ok) {
        console.error("Error desde la API:", respuesta.status, data);

        // Token vencido o inválido: se limpia la sesión y se manda al login.
        if (respuesta.status === 401 && autenticado) {
            cerrarSesion();
            throw crearError("Tu sesión expiró. Inicia sesión de nuevo.", 401);
        }
        throw crearError(mensajeDeError(data, respuesta.status), respuesta.status);
    }

    return data;
}
