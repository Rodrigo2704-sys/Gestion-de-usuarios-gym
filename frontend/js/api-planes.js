// ====================================================================================
// api-planes.js  (requiere api-base.js cargado antes)
//
// Manejo de Planes y Membresías:
//  - Las rutas que reciben datos sensibles en la URL usan encodeURIComponent().
//  - Los métodos POST y PUT envían los datos en el 'cuerpo' (JSON).
// ====================================================================================

/** POST /planes/crear  (solo admin). datosPlan: { tipo, precio, duracion }  (duracion en días) */
function apiCreacionPlan(datosPlan) {
    return apiFetch("/planes/crear", { 
        metodo: "POST", 
        cuerpo: datosPlan 
    });
}

/** GET /planes/obtener  (cualquier usuario autenticado) */
function apiObtenerPlanesActivos() {
    return apiFetch("/planes/obtener");
}

/** POST /planes/asignar  (solo admin). datosMembresia: { usuario_id, plan_id } */
function apiAsignarMembresia(datosMembresia) {
    return apiFetch("/planes/asignar", { 
        metodo: "POST", 
        cuerpo: datosMembresia 
    });
}

/** PUT /planes/actualizar-plan/{usuario_id}  (solo admin). datosActualizados: { plan_id?, estado? } */
function apiActualizarMembresia(usuario_id, datosActualizados) {
    /* 
      ¿POR QUÉ ENCODEURICOMPONENT AQUÍ?
      El 'usuario_id' es un parámetro dinámico que se inyecta directamente dentro de la ruta (URL).
      Usamos encodeURIComponent() para asegurarnos de que la URL se arme limpia y segura.
    */
    return apiFetch(`/planes/actualizar-plan/${encodeURIComponent(usuario_id)}`, {
        metodo: "PUT",
        cuerpo: datosActualizados
    });
}

/** GET /planes/mi-membresia  -> lista con TODAS las membresías del usuario (la más reciente primero) */
function apiVerMembresia() {
    return apiFetch("/planes/mi-membresia");
}