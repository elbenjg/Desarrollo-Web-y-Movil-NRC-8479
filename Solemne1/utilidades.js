function formatoCLP(numero) {
    return "$" + Number(numero).toLocaleString("es-CL");
}


function validarCorreo(correo) {
    const patron = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return patron.test(String(correo).trim());
}


function validarRut(rutSucio) {
    if (!rutSucio) return false;
    let rut = String(rutSucio).replace(/[.\s]/g, "").toUpperCase();
    if (!/^\d{7,8}-[0-9K]$/.test(rut)) return false;
    const [cuerpo, dv] = rut.split("-");
    let suma = 0;
    let multiplo = 2;
    for (let i = cuerpo.length - 1; i >= 0; i--) {
        suma += Number(cuerpo[i]) * multiplo;
        multiplo = multiplo === 7 ? 2 : multiplo + 1;
    }
    const resto = 11 - (suma % 11);
    let dvEsperado = String(resto);
    if (resto === 11) dvEsperado = "0";
    if (resto === 10) dvEsperado = "K";
    return dvEsperado === dv;
}

function formatearRutMientrasEscribe(input) {
    let valor = input.value.replace(/[^0-9kK]/g, "").toUpperCase();
    if (valor.length > 1) {
        const dv = valor.slice(-1);
        let cuerpo = valor.slice(0, -1);
        cuerpo = cuerpo.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        input.value = cuerpo + "-" + dv;
    } else {
        input.value = valor;
    }
}

function mostrarError(idInput, idError, mensaje) {
    const input = document.getElementById(idInput);
    const error = document.getElementById(idError);
    if (input) input.classList.add("is-invalid");
    if (error) {
        error.textContent = mensaje;
        error.classList.add("mostrar");
    }
}

function limpiarError(idInput, idError) {
    const input = document.getElementById(idInput);
    const error = document.getElementById(idError);
    if (input) input.classList.remove("is-invalid");
    if (error) error.classList.remove("mostrar");
}