// ====================================================================================
// api-usuarios.js  (requiere api-base.js cargado antes)
//
// Sobre el body en cada método HTTP:
//  - POST, PUT y PATCH llevan body (el JSON con los datos a crear o modificar).
//  - GET no lleva body (fetch lo prohíbe): lo que necesita viaja en la URL.
//  - DELETE normalmente tampoco: el ID va en la URL.
//  - PUT reemplaza el recurso completo; PATCH modifica solo los campos enviados.
//    Tu backend de usuarios usa PATCH.
// ====================================================================================

/** POST /usuarios/login  (pública; FastAPI espera un formulario, no JSON) */
async function apiIniciarSesion(correo, password) {
    const datos = new URLSearchParams();
    datos.append("username", correo); // OAuth2PasswordRequestForm llama "username" al correo
    datos.append("password", password);

    const data = await apiFetch("/usuarios/login", {
        metodo: "POST",
        cuerpo: datos,
        autenticado: false,
        formulario: true
    });

    localStorage.setItem("token", data.access_token);
    localStorage.setItem("nombre_usuario", data.nombre);
    localStorage.setItem("rol", data.rol);
    return data;
}

/** POST /usuarios/registrar  (pública) */
function apiRegistrarUsuario(datosUsuario) {
    return apiFetch("/usuarios/registrar", {
        metodo: "POST",
        cuerpo: datosUsuario,
        autenticado: false
    });
}

/** GET /usuarios/  (solo admin) */
function apiListarUsuarios(skip = 0, limit = 100) {
    // La barra final evita que FastAPI responda con una redirección 307.
    return apiFetch(`/usuarios/?skip=${skip}&limit=${limit}`);
}

/** GET /usuarios/{id}  (el dueño o un admin) */
function apiObtenerUsuarioPorId(usuarioId) {
    /* 
      ¿CUÁNDO SE USA? 
      Se usa cuando un dato es dinámico (cambia según el usuario) y se mete dentro de la barra '/'.
      
      ¿PARA QUÉ SIRVE? 
      Traduce caracteres especiales o espacios para que la dirección web no se rompa.
    */
    return apiFetch(`/usuarios/${encodeURIComponent(usuarioId)}`);
}

/** PATCH /usuarios/{id}  (el dueño o un admin). Solo nombre y correo. */
function apiModificarUsuario(usuarioId, datosActualizacion) {
    return apiFetch(`/usuarios/${encodeURIComponent(usuarioId)}`, {
        metodo: "PATCH",
        cuerpo: datosActualizacion
    });
}

/** DELETE /usuarios/{id}  (solo admin) */
function apiBorrarUsuario(usuarioId) {
    return apiFetch(`/usuarios/${encodeURIComponent(usuarioId)}`, { metodo: "DELETE" });
}

/** GET /usuarios/buscar/correo?email=...  (solo admin) */
function apiObtenerUsuarioPorCorreo(correoElectronico) {
    /* 
      ¿CUÁNDO SE USA? 
      Se usa obligatoriamente cuando un texto escrito por el usuario (como un correo con '@' o '+') 
      va colocado después del signo de interrogación '?' en una petición GET.
      
      ¿PARA QUÉ SIRVE? 
      Blindar la URL para que los símbolos del correo no confundan al servidor.
    */
    return apiFetch(`/usuarios/buscar/correo?email=${encodeURIComponent(correoElectronico)}`);
}

/** PATCH /usuarios/{id}/cambiar-rol?nuevo_rol_id=...  (solo admin; 1 = Admin, 2 = Cliente) */
function apiCambiarRol(usuarioId, nuevoRolId) {
    // Nota: usuarioId lleva encodeURIComponent porque es una variable en la ruta. 
    // nuevoRolId NO lo lleva porque es un número fijo de opción que manejamos nosotros.
    return apiFetch(`/usuarios/${encodeURIComponent(usuarioId)}/cambiar-rol?nuevo_rol_id=${nuevoRolId}`, {
        metodo: "PATCH"
    });
}

/** POST /usuarios/cambiar-password  (usuario autenticado; pide la contraseña actual) */
function apiCambiarPassword(passwordActual, passwordNueva) {
    return apiFetch("/usuarios/cambiar-password", {
        metodo: "POST",
        cuerpo: { password_actual: passwordActual, password_nueva: passwordNueva }
    });
}

// ------------------------------------------------------------------------------------
// Verificación de correo y recuperación de contraseña (rutas públicas: sin token).
// Todas devuelven { Exito, Mensaje }. Los errores llegan con error.status y error.message.
// ------------------------------------------------------------------------------------

/** POST /usuarios/verificar-correo  (código de 6 dígitos enviado al registrarse) */
function apiVerificarCorreo(correo, codigo) {
    return apiFetch("/usuarios/verificar-correo", {
        metodo: "POST",
        cuerpo: { correo, codigo },
        autenticado: false
    });
}

/** POST /usuarios/reenviar-codigo  (siempre responde lo mismo, exista o no el correo) */
function apiReenviarCodigo(correo) {
    return apiFetch("/usuarios/reenviar-codigo", {
        metodo: "POST",
        cuerpo: { correo },
        autenticado: false
    });
}

/** POST /usuarios/olvide-password  (paso 1: pide el código de recuperación) */
function apiOlvidePassword(correo) {
    return apiFetch("/usuarios/olvide-password", {
        metodo: "POST",
        cuerpo: { correo },
        autenticado: false
    });
}

/** POST /usuarios/restablecer-password  (paso 2: código + contraseña nueva) */
function apiRestablecerPassword(correo, codigo, passwordNueva) {
    return apiFetch("/usuarios/restablecer-password", {
        metodo: "POST",
        cuerpo: { correo, codigo, password_nueva: passwordNueva },
        autenticado: false
    });
}
