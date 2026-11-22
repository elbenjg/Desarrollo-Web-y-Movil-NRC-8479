function mostrarAvisoFlotante(texto) {
    let aviso = document.getElementById("aviso-flotante");
    if (!aviso) {
        aviso = document.createElement("div");
        aviso.id = "aviso-flotante";
        aviso.style.position = "fixed";
        aviso.style.bottom = "24px";
        aviso.style.right = "24px";
        aviso.style.backgroundColor = "#35231D";
        aviso.style.color = "#C09A72";
        aviso.style.padding = "14px 22px";
        aviso.style.borderRadius = "12px";
        aviso.style.boxShadow = "0 4px 14px rgba(0,0,0,0.35)";
        aviso.style.zIndex = "9999";
        aviso.style.fontWeight = "600";
        aviso.style.transition = "opacity 0.4s ease";
        document.body.appendChild(aviso);
    }
    aviso.textContent = texto;
    aviso.style.opacity = "1";
    clearTimeout(aviso._timeout);
    aviso._timeout = setTimeout(() => { aviso.style.opacity = "0"; }, 2200);
}

function obtenerCarrito() {
    try {
        return JSON.parse(localStorage.getItem(LS_CARRITO)) || [];
    } catch (e) {
        return [];
    }
}

function guardarCarrito(carrito) {
    localStorage.setItem(LS_CARRITO, JSON.stringify(carrito));
    actualizarBadgeCarrito();
}

function agregarAlCarrito(idProducto, cantidad = 1) {
    const carrito = obtenerCarrito();
    const item = carrito.find(i => i.id === Number(idProducto));
    if (item) {
        item.cantidad += cantidad;
    } else {
        carrito.push({ id: Number(idProducto), cantidad: cantidad });
    }
    guardarCarrito(carrito);
    mostrarAvisoFlotante("¡Producto añadido al carrito!");
}

function quitarDelCarrito(idProducto) {
    let carrito = obtenerCarrito();
    carrito = carrito.filter(i => i.id !== Number(idProducto));
    guardarCarrito(carrito);
    if (document.getElementById("contenedor-carrito")) renderizarCarrito();
}

function cambiarCantidadCarrito(idProducto, cantidad) {
    const carrito = obtenerCarrito();
    const item = carrito.find(i => i.id === Number(idProducto));
    if (!item) return;
    item.cantidad = Math.max(1, Number(cantidad) || 1);
    guardarCarrito(carrito);
    if (document.getElementById("contenedor-carrito")) renderizarCarrito();
}

/** Une el carrito (id + cantidad) con los datos del producto. */
function obtenerCarritoDetallado() {
    return obtenerCarrito()
        .map(item => {
            const producto = obtenerProductoPorId(item.id);
            if (!producto) return null;
            return {
                ...producto,
                cantidad: item.cantidad,
                subtotal: producto.precio * item.cantidad
            };
        })
        .filter(Boolean);
}

function calcularTotalCarrito() {
    return obtenerCarritoDetallado().reduce((acc, i) => acc + i.subtotal, 0);
}

function contarItemsCarrito() {
    return obtenerCarrito().reduce((acc, i) => acc + i.cantidad, 0);
}

function actualizarBadgeCarrito() {
    const badge = document.getElementById("badge-carrito");
    if (!badge) return;
    const total = contarItemsCarrito();
    badge.textContent = total;
    badge.style.display = total > 0 ? "inline-block" : "none";
}