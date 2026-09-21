function renderizarProductos() {
    const contenedor = document.getElementById("contenedor-productos");
    if (!contenedor) return;

    const productos = obtenerProductos();
    const categorias = [...new Set(productos.map(p => p.categoria))];

    contenedor.innerHTML = categorias
        .map(categoria => {
            const items = productos.filter(p => p.categoria === categoria);
            const tarjetas = items
                .map(
                    p => `
                <div class="col-sm-6 col-md-4 col-lg-3">
                    <div class="tarjeta-producto">
                        <img src="${p.imagen}" alt="${p.nombre}">
                        <div class="cuerpo">
                            <div class="categoria">${p.categoria}</div>
                            <div class="nombre">${p.nombre}</div>
                            <div class="precio">${formatoCLP(p.precio)}</div>
                            <button type="button" class="btn-marca mt-3" onclick="agregarAlCarrito(${p.id})">
                                Agregar al carrito
                            </button>
                        </div>
                    </div>
                </div>`
                )
                .join("");
            return `
                <h3 class="subtitulo fs-3 text-start mb-3 mt-4">${categoria}</h3>
                <div class="row g-4 mb-2">${tarjetas}</div>`;
        })
        .join("");
}

function renderizarCarrito() {
    const contenedor = document.getElementById("contenedor-carrito");
    if (!contenedor) return;

    const items = obtenerCarritoDetallado();
    const totalEl = document.getElementById("total-carrito");
    const btnPagar = document.getElementById("btn-pasar-pago");

    if (items.length === 0) {
        contenedor.innerHTML = `
            <p class="fs-5">Tu carrito está vacío.</p>
            <a href="pedidos_online.html" class="btn-marca-outline">Ver catálogo</a>`;
        if (totalEl) totalEl.textContent = formatoCLP(0);
        if (btnPagar) btnPagar.disabled = true;
        return;
    }

    contenedor.innerHTML = items
        .map(
            i => `
        <div class="fila-carrito d-flex align-items-center justify-content-between mb-2" data-id="${i.id}">
            <div class="flex-grow-1 text-start">
                <div class="fw-bold">${i.nombre}</div>
                <div class="text-muted small">${formatoCLP(i.precio)} c/u</div>
            </div>
            <input type="number" min="1" value="${i.cantidad}"
                   onchange="cambiarCantidadCarrito(${i.id}, this.value)">
            <div class="fw-bold mx-3" style="min-width:90px;">${formatoCLP(i.subtotal)}</div>
            <button type="button" class="btn btn-sm btn-outline-danger" onclick="quitarDelCarrito(${i.id})">
                &times;
            </button>
        </div>`
        )
        .join("");

    if (totalEl) totalEl.textContent = formatoCLP(calcularTotalCarrito());
    if (btnPagar) btnPagar.disabled = false;
}