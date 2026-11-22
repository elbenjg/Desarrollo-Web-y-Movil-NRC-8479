// Pantalla de inventario (P12): el admin agrega, edita y elimina productos; el admin y el dueño cambian stock y disponibilidad.
let productoEnEdicion = null;

function mostrarAviso(tipo, texto) {
    const aviso = document.getElementById("aviso-inventario");
    aviso.className = `alert alert-${tipo}`;
    aviso.textContent = texto;
}

function avisarError(error) {
    mostrarAviso("danger", `${error.message} (ref. ${error.correlacion})`);
}

function celda(contenido, clase = "") {
    const td = document.createElement("td");
    td.className = clase;
    if (contenido instanceof Node) td.append(contenido);
    else td.textContent = contenido;
    return td;
}

function crearBoton(texto, clase, accion) {
    const boton = document.createElement("button");
    boton.type = "button";
    boton.className = `btn btn-sm ${clase}`;
    boton.textContent = texto;
    boton.addEventListener("click", () => accion(boton));
    return boton;
}

function filaProducto(producto) {
    const stock = document.createElement("input");
    stock.type = "number";
    stock.min = "0";
    stock.max = "100000";
    stock.step = "1";
    stock.className = "form-control form-control-sm";
    stock.value = producto.stock;
    stock.setAttribute("aria-label", `Stock de ${producto.nombre}`);

    const disponible = document.createElement("input");
    disponible.type = "checkbox";
    disponible.className = "form-check-input";
    disponible.checked = producto.disponible;
    disponible.setAttribute("aria-label", `${producto.nombre} disponible`);

    const acciones = document.createElement("div");
    acciones.className = "d-flex flex-wrap gap-1";
    acciones.append(crearBoton("Guardar", "btn-success", () => guardarDisponibilidad(producto, stock, disponible)));
    if (tieneRol("admin")) {
        acciones.append(crearBoton("Editar", "btn-outline-secondary", () => editarProducto(producto)));
        acciones.append(crearBoton("Eliminar", "btn-outline-danger", (boton) => eliminarProducto(producto, boton)));
    }

    const fila = document.createElement("tr");
    fila.dataset.id = producto.id;
    fila.append(
        celda(producto.id), celda(producto.nombre), celda(producto.categoria),
        celda(formatoCLP(producto.precio), "text-end"), celda(stock), celda(disponible), celda(acciones),
    );
    return fila;
}

async function cargarInventario() {
    const estado = document.getElementById("estado-inventario");
    const tabla = document.getElementById("tabla-inventario");
    estado.textContent = "Cargando inventario…";
    estado.classList.remove("d-none");
    tabla.classList.add("d-none");
    try {
        const productos = await llamarApi("GET", "/products");
        if (productos.length === 0) {
            estado.textContent = "No hay productos en el inventario.";
            return;
        }
        document.getElementById("cuerpo-inventario").replaceChildren(...productos.map(filaProducto));
        estado.classList.add("d-none");
        tabla.classList.remove("d-none");
    } catch (error) {
        estado.textContent = `No se pudo cargar el inventario: ${error.message} (ref. ${error.correlacion})`;
    }
}

async function guardarDisponibilidad(producto, inputStock, inputDisponible) {
    const stock = Number(inputStock.value);
    if (inputStock.value === "" || !Number.isInteger(stock) || stock < 0 || stock > 100000) {
        mostrarAviso("warning", `El stock de ${producto.nombre} debe ser un número entero entre 0 y 100.000.`);
        return;
    }
    try {
        await llamarApi("PATCH", `/products/${producto.id}/availability`, { disponible: inputDisponible.checked, stock });
        mostrarAviso("success", `Se actualizó ${producto.nombre}.`);
        await cargarInventario();
    } catch (error) {
        avisarError(error);
    }
}

function reiniciarFormulario() {
    productoEnEdicion = null;
    document.getElementById("form-producto").reset();
    document.getElementById("titulo-producto").textContent = "Nuevo producto";
    document.getElementById("boton-guardar-producto").textContent = "Agregar producto";
    document.getElementById("boton-cancelar-edicion").classList.add("d-none");
}

function editarProducto(producto) {
    productoEnEdicion = producto.id;
    document.getElementById("producto-nombre").value = producto.nombre;
    document.getElementById("producto-categoria").value = producto.categoria;
    document.getElementById("producto-precio").value = producto.precio;
    document.getElementById("producto-stock").value = producto.stock;
    document.getElementById("producto-imagen").value = producto.imagen || "";
    document.getElementById("producto-descripcion").value = producto.descripcion || "";
    document.getElementById("producto-disponible").checked = producto.disponible;
    document.getElementById("titulo-producto").textContent = `Editar producto ${producto.id}`;
    document.getElementById("boton-guardar-producto").textContent = "Guardar cambios";
    document.getElementById("boton-cancelar-edicion").classList.remove("d-none");
    document.getElementById("seccion-producto").scrollIntoView({ behavior: "smooth" });
}

async function guardarProducto(evento) {
    evento.preventDefault();
    const boton = document.getElementById("boton-guardar-producto");
    const datos = {
        nombre: document.getElementById("producto-nombre").value.trim(),
        categoria: document.getElementById("producto-categoria").value.trim(),
        precio: Number(document.getElementById("producto-precio").value),
        stock: Number(document.getElementById("producto-stock").value),
        imagen: document.getElementById("producto-imagen").value.trim(),
        descripcion: document.getElementById("producto-descripcion").value.trim(),
        disponible: document.getElementById("producto-disponible").checked,
    };
    boton.disabled = true;
    try {
        if (productoEnEdicion === null) {
            const creado = await llamarApi("POST", "/products", datos);
            mostrarAviso("success", `Se agregó ${creado.nombre} con el ID ${creado.id}.`);
        } else {
            await llamarApi("PUT", `/products/${productoEnEdicion}`, datos);
            mostrarAviso("success", `Se guardaron los cambios de ${datos.nombre}.`);
        }
        reiniciarFormulario();
        await cargarInventario();
    } catch (error) {
        avisarError(error);
    } finally {
        boton.disabled = false;
    }
}

async function eliminarProducto(producto, boton) {
    if (boton.dataset.confirmar !== "si") {
        boton.dataset.confirmar = "si";
        boton.textContent = "¿Confirmar?";
        setTimeout(() => { boton.dataset.confirmar = ""; boton.textContent = "Eliminar"; }, 4000);
        return;
    }
    boton.disabled = true;
    try {
        await llamarApi("DELETE", `/products/${producto.id}`);
        mostrarAviso("success", `Se eliminó ${producto.nombre}.`);
        if (productoEnEdicion === producto.id) reiniciarFormulario();
        await cargarInventario();
    } catch (error) {
        boton.disabled = false;
        avisarError(error);
    }
}

function configurarInventario() {
    const estado = document.getElementById("estado-inventario");
    if (!estado) return;
    if (!obtenerSesion()) {
        estado.replaceChildren("Para ver el inventario debes ", crearEnlace("iniciar_sesion.html", "iniciar sesión"),
            " con una cuenta de administrador o dueño.");
        return;
    }
    if (!tieneRol("admin", "dueno")) {
        estado.textContent = "Tu cuenta no tiene permiso para administrar el inventario.";
        return;
    }
    if (tieneRol("admin")) {
        document.getElementById("seccion-producto").classList.remove("d-none");
        document.getElementById("form-producto").addEventListener("submit", guardarProducto);
        document.getElementById("boton-cancelar-edicion").addEventListener("click", reiniciarFormulario);
    }
    cargarInventario();
}

document.addEventListener("DOMContentLoaded", configurarInventario);
