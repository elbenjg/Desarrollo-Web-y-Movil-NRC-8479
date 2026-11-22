// Conexión del frontend con el API Gateway: sesión del usuario, llamadas a la API y enlaces de la cuenta.
const API_URL = "http://127.0.0.1:8000/api/v1";
const CLAVE_SESION = "fn_sesion";

class ErrorApi extends Error {
    constructor(estado, mensaje, correlacion) {
        super(mensaje);
        this.estado = estado;
        this.correlacion = correlacion;
    }
}

function obtenerSesion() {
    try {
        const sesion = JSON.parse(sessionStorage.getItem(CLAVE_SESION));
        if (sesion && sesion.expira > Date.now()) return sesion;
    } catch (e) { }
    sessionStorage.removeItem(CLAVE_SESION);
    return null;
}

function guardarSesion(datos, correo) {
    sessionStorage.setItem(CLAVE_SESION, JSON.stringify({
        token: datos.access_token,
        roles: datos.roles,
        correo: correo,
        expira: Date.now() + datos.expires_in * 1000,
    }));
}

function tieneRol(...roles) {
    const sesion = obtenerSesion();
    return !!sesion && sesion.roles.some((rol) => roles.includes(rol));
}

function mensajeDeError(datos) {
    if (datos && typeof datos.detail === "string") return datos.detail;
    if (datos && Array.isArray(datos.detail)) {
        return "Revisa los datos: " + datos.detail.map((e) => `${e.loc[e.loc.length - 1]} (${e.msg})`).join("; ");
    }
    return "Ocurrió un error inesperado. Inténtalo de nuevo.";
}

async function llamarApi(metodo, ruta, cuerpo) {
    const sesion = obtenerSesion();
    const correlacion = crypto.randomUUID();
    const cabeceras = { "X-Correlation-Id": correlacion };
    if (cuerpo !== undefined) cabeceras["Content-Type"] = "application/json";
    if (sesion) cabeceras.Authorization = "Bearer " + sesion.token;

    let respuesta;
    try {
        respuesta = await fetch(API_URL + ruta, {
            method: metodo,
            headers: cabeceras,
            body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
        });
    } catch (e) {
        console.warn(`[FN] ${metodo} ${ruta} -> sin conexión cid=${correlacion}`);
        throw new ErrorApi(0, "No se pudo conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.", correlacion);
    }
    console.info(`[FN] ${metodo} ${ruta} -> ${respuesta.status} cid=${correlacion}`);

    const datos = respuesta.status === 204 ? null : await respuesta.json().catch(() => null);
    if (respuesta.ok) return datos;
    if (respuesta.status === 401 && sesion) {
        sessionStorage.removeItem(CLAVE_SESION);
        location.href = "iniciar_sesion.html?expirada=1";
    }
    throw new ErrorApi(respuesta.status, mensajeDeError(datos), correlacion);
}

function crearEnlace(href, texto) {
    const enlace = document.createElement("a");
    enlace.href = href;
    enlace.textContent = texto;
    return enlace;
}

function actualizarEnlacesSesion() {
    const contenedor = document.getElementById("top-auth-links");
    const sesion = obtenerSesion();
    if (!contenedor || !sesion) return;

    const usuario = document.createElement("span");
    usuario.textContent = sesion.correo;
    const salir = crearEnlace("#", "Cerrar sesión");
    salir.id = "link-cerrar-sesion";
    salir.addEventListener("click", async (evento) => {
        evento.preventDefault();
        try { await llamarApi("POST", "/auth/logout"); } catch (e) { }
        sessionStorage.removeItem(CLAVE_SESION);
        location.href = "index.html";
    });

    contenedor.replaceChildren();
    if (tieneRol("admin", "dueno")) contenedor.append(crearEnlace("inventario.html", "Inventario"));
    contenedor.append(usuario, salir);
}
