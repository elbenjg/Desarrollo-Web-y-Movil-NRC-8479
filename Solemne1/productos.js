
const LS_CARRITO = "fn_carrito";
const LS_CLIENTES = "fn_clientes";
const LS_SESION = "fn_sesion";
const LS_BOLETAS = "fn_boletas";
const LS_CONTADOR_BOLETA = "fn_contador_boleta";
const LS_ENVIO = "fn_envio";

const productosPorDefecto = [
    {
        "id": 1,
        "nombre": "Cono Vainilla Crunch",
        "categoria": "Conos Clásicos",
        "precio": 3500,
        "imagen": "https://static.vecteezy.com/system/resources/thumbnails/015/762/278/small/vanilla-ice-cream-scoop-in-a-waffle-cone-photo.jpg"
    },
    {
        "id": 2,
        "nombre": "Cono Chocolate Suizo",
        "categoria": "Conos Clásicos",
        "precio": 3800,
        "imagen": "https://images.unsplash.com/photo-1559703248-dcaaec9fab78?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60"
    },
    {
        "id": 3,
        "nombre": "Copa Frutos Rojos",
        "categoria": "Especialidades",
        "precio": 5200,
        "imagen": "https://es.hellorecipes.net/thumb/768/helado-de-frutos-rojos-saludable.webp"
    },
    {
        "id": 4,
        "nombre": "Banana Split",
        "categoria": "Especialidades",
        "precio": 6500,
        "imagen": "https://thumbs.dreamstime.com/b/banana-split-sundae-dessert-umbrella-48261592.jpg"
    },
    {
        "id": 5,
        "nombre": "Pote Familiar 1L",
        "categoria": "Para Llevar",
        "precio": 12900,
        "imagen": "https://images.unsplash.com/photo-1501443762994-82bd5dace89a?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60"
    },
    {
        "id": 6,
        "nombre": "Cono Pistacho",
        "categoria": "Conos Clásicos",
        "precio": 4200,
        "imagen": "https://thumbs.dreamstime.com/b/una-bola-de-helado-pistacho-en-un-cono-waffle-rodeada-pistachos-crujientes-sobre-superficie-verde-brillante-imagen-creada-con-420490286.jpg"
    },
    {
        "id": 7,
        "nombre": "Envase 500ml Chocolate",
        "categoria": "Para Llevar",
        "precio": 7900,
        "imagen": "https://img.magnific.com/fotos-premium/tres-cucharadas-helado-chocolate-taza-marron_1077802-451766.jpg?semt=ais_hybrid&w=740&q=80"
    }
];


function obtenerProductos() {
    return productosPorDefecto;
}

function obtenerProductoPorId(id) {
    return obtenerProductos().find(p => p.id === Number(id));
}
