// js/login/login.js 
// (Requiere que api-base.js y api-usuarios.js estén cargados previamente en el HTML)

// 1. Configuración de rutas de navegación
const PAGINA_ADMIN = "usuarios.html";   // Vista del panel de administración
const PAGINA_CLIENTE = "cliente.html"; // Vista para los clientes normales

// 2. Escuchamos el evento de envío (submit) del formulario de inicio de sesión
document.getElementById("iniciarsesion").addEventListener("submit", async function (e) {
    // Prevenimos que el navegador recargue la página automáticamente
    e.preventDefault(); 

    // 3. Captura y limpieza de los datos ingresados por el usuario
    const correo = document.getElementById("correo").value.trim(); // Se remueven espacios al inicio y al final
    const password = document.getElementById("password").value;    // La contraseña conserva espacios exactos

    // 4. Bloqueo del botón de envío para evitar peticiones duplicadas por múltiple clic
    const botonSubmit = e.target.querySelector("button[type='submit']");
    if (botonSubmit) botonSubmit.disabled = true;

    try {
        // 5. Petición asíncrona a la API para autenticar al usuario
        // apiIniciarSesion hace el POST y guarda el token, nombre y rol en el localStorage
        const data = await apiIniciarSesion(correo, password);

        // 6. Verificación del rol retornado por la API
        // Se convierte el rol a texto, se pasa a minúsculas y se evalúa si empieza por "admin"
        const esAdmin = String(data.rol).toLowerCase().startsWith("admin");
        
        // Redirección a la pantalla correspondiente según el nivel de permisos
        window.location.href = esAdmin ? PAGINA_ADMIN : PAGINA_CLIENTE;

    } catch (error) {
        // 7. Manejo de excepciones y respuestas de error
        
        // Si el código de estado es 403, significa que las credenciales son correctas 
        // pero la cuenta requiere verificación de correo
        if (error.estado === 403) {
            alert(error.message);
            // Se redirige a la página de verificación enviando el correo codificado en la URL
            window.location.href = `verificar.html?correo=${encodeURIComponent(correo)}`;
            return;
        }
        
        // Muestra un aviso emergente para otros errores (ej. 401 Credenciales inválidas)
        alert("Error de autenticación: " + error.message);

    } finally {
        // 8. Se ejecuta siempre al terminar la operación (éxito o error)
        // Se reactiva el botón de envío para permitir nuevos intentos
        if (botonSubmit) botonSubmit.disabled = false;
    }
});