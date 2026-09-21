function configurarFormularioRegistro() {
    const form = document.getElementById("form-registro");
    if (!form) return;

    const inputRun = document.getElementById("input-run");
    if (inputRun) inputRun.addEventListener("input", () => formatearRutMientrasEscribe(inputRun));

    form.addEventListener("submit", (evento) => {
        evento.preventDefault();
        [
            ["input-nombre", "error-nombre"], ["input-run", "error-run"], ["input-direccion", "error-direccion"],
            ["input-comuna", "error-comuna"], ["input-region", "error-region"], ["input-provincia", "error-provincia"],
            ["input-nacimiento", "error-nacimiento"], ["input-sexo", "error-sexo"], ["input-correo", "error-correo"],
            ["input-telefono", "error-telefono"], ["input-clave", "error-clave"], ["input-clave2", "error-clave2"]
        ].forEach(([i, e]) => limpiarError(i, e));
        document.getElementById("error-general").classList.remove("mostrar");

        const datos = {
            nombreCompleto: document.getElementById("input-nombre").value.trim(),
            run: document.getElementById("input-run").value.trim(),
            direccion: document.getElementById("input-direccion").value.trim(),
            comuna: document.getElementById("input-comuna").value.trim(),
            region: document.getElementById("input-region").value.trim(),
            provincia: document.getElementById("input-provincia").value.trim(),
            fechaNacimiento: document.getElementById("input-nacimiento").value,
            sexo: document.getElementById("input-sexo").value,
            correo: document.getElementById("input-correo").value.trim(),
            telefono: document.getElementById("input-telefono").value.trim(),
            clave: document.getElementById("input-clave").value,
        };
        const clave2 = document.getElementById("input-clave2").value;

        let valido = true;
        if (!datos.nombreCompleto) { mostrarError("input-nombre", "error-nombre", "Ingresa tu nombre completo."); valido = false; }
        if (!validarRut(datos.run)) { mostrarError("input-run", "error-run", "RUT inválido. Formato: 12.345.678-5."); valido = false; }
        if (!datos.direccion) { mostrarError("input-direccion", "error-direccion", "Ingresa tu dirección."); valido = false; }
        if (!datos.comuna) { mostrarError("input-comuna", "error-comuna", "Ingresa tu comuna."); valido = false; }
        if (!datos.region) { mostrarError("input-region", "error-region", "Ingresa tu región."); valido = false; }
        if (!datos.provincia) { mostrarError("input-provincia", "error-provincia", "Ingresa tu provincia."); valido = false; }
        if (!datos.fechaNacimiento) { mostrarError("input-nacimiento", "error-nacimiento", "Ingresa tu fecha de nacimiento."); valido = false; }
        if (!datos.sexo) { mostrarError("input-sexo", "error-sexo", "Selecciona una opción."); valido = false; }
        if (!validarCorreo(datos.correo)) { mostrarError("input-correo", "error-correo", "Ingresa un correo válido."); valido = false; }
        if (!datos.telefono) { mostrarError("input-telefono", "error-telefono", "Ingresa tu número telefónico."); valido = false; }
        if (!datos.clave || datos.clave.length < 6) { mostrarError("input-clave", "error-clave", "La contraseña debe tener al menos 6 caracteres."); valido = false; }
        if (datos.clave !== clave2) { mostrarError("input-clave2", "error-clave2", "Las contraseñas no coinciden."); valido = false; }

        if (!valido) return;

        // NOTA: por ahora el registro no hace nada más que validar el
        // formulario. Guardar la cuenta y dejarte con sesión iniciada es
        // trabajo del backend, que se implementará en la siguiente etapa.
    });
}

/** iniciar_sesion.html */
function configurarFormularioLogin() {
    const form = document.getElementById("form-login");
    if (!form) return;

    form.addEventListener("submit", (evento) => {
        evento.preventDefault();
        limpiarError("input-login-correo", "error-login-correo");
        limpiarError("input-login-clave", "error-login-clave");

        const correo = document.getElementById("input-login-correo").value.trim();
        const clave = document.getElementById("input-login-clave").value;
        let valido = true;
        if (!validarCorreo(correo)) { mostrarError("input-login-correo", "error-login-correo", "Ingresa un correo válido."); valido = false; }
        if (!clave) { mostrarError("input-login-clave", "error-login-clave", "Ingresa tu contraseña."); valido = false; }
        if (!valido) return;

        // NOTA: por ahora iniciar sesión no hace nada más que validar el
        // formulario. Comprobar la cuenta y dejar la sesión iniciada es
        // trabajo del backend, que se implementará en la siguiente etapa.
    });
}

function configurarFormularioEnvio() {
    const form = document.getElementById("form-envio");
    const btnPagar = document.getElementById("btn-pasar-pago");
    if (!form || !btnPagar) return;

    btnPagar.addEventListener("click", () => {

        if (obtenerCarrito().length === 0) return;

        ["input-envio-comuna", "input-envio-direccion", "input-envio-region", "input-envio-provincia"].forEach(id =>
            limpiarError(id, id.replace("input-", "error-"))
        );

        const envio = {
            comuna: document.getElementById("input-envio-comuna").value.trim(),
            direccion: document.getElementById("input-envio-direccion").value.trim(),
            region: document.getElementById("input-envio-region").value.trim(),
            provincia: document.getElementById("input-envio-provincia").value.trim(),
        };
        let valido = true;
        Object.entries(envio).forEach(([campo, valor]) => {
            if (!valor) {
                mostrarError("input-envio-" + campo, "error-envio-" + campo, "Este campo es obligatorio.");
                valido = false;
            }
        });
        if (!valido) return;

        window.location.href = "pago.html";
    });
}

/** pago.html */
function configurarFormularioPago() {
    const form = document.getElementById("form-pago");
    if (!form) return;

    const resumen = document.getElementById("resumen-pago");
    if (resumen) {
        const items = obtenerCarritoDetallado();
        if (items.length === 0) {
            window.location.href = "carrito.html";
            return;
        }
        resumen.innerHTML = items
            .map(i => `<div class="d-flex justify-content-between"><span>${i.nombre} x${i.cantidad}</span><span>${formatoCLP(i.subtotal)}</span></div>`)
            .join("") +
            `<hr><div class="d-flex justify-content-between fs-5 fw-bold"><span>Total</span><span>${formatoCLP(calcularTotalCarrito())}</span></div>`;
    }

    form.addEventListener("submit", (evento) => {
        evento.preventDefault();
        const metodoSeleccionado = form.querySelector('input[name="metodo-pago"]:checked');
        const errorMetodo = document.getElementById("error-metodo-pago");
        if (!metodoSeleccionado) {
            if (errorMetodo) errorMetodo.classList.add("mostrar");
            return;
        }
        if (errorMetodo) errorMetodo.classList.remove("mostrar");

    });
}

/** contacto.html */
function configurarFormularioContacto() {
    const form = document.getElementById("form-contacto");
    if (!form) return;
    form.addEventListener("submit", (evento) => {
        evento.preventDefault();
        const nombre = document.getElementById("input-contacto-nombre").value.trim();
        form.reset();
        const confirmacion = document.getElementById("confirmacion-contacto");
        confirmacion.textContent = "¡Gracias " + (nombre || "") + "! Recibimos tu mensaje y te responderemos a la brevedad.";
        confirmacion.classList.remove("d-none");
    });
}