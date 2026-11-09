# Script de creación: índices de cada base y datos de prueba ficticios.
# Uso: py backend/seed.py          -> crea índices y carga datos solo si las colecciones están vacías
#      py backend/seed.py --reset  -> borra las bases fn_* y las vuelve a crear
import sys
from datetime import datetime, timezone

from pymongo import ASCENDING, MongoClient

from comun import MONGODB_URI, hash_clave

CLAVE_DEMO = "Demo1234"

PRODUCTOS = [
    (
        1,
        "Cono Vainilla Crunch",
        "Conos Clásicos",
        3500,
        "https://static.vecteezy.com/system/resources/thumbnails/015/762/278/small/vanilla-ice-cream-scoop-in-a-waffle-cone-photo.jpg",
    ),
    (
        2,
        "Cono Chocolate Suizo",
        "Conos Clásicos",
        3800,
        "https://images.unsplash.com/photo-1559703248-dcaaec9fab78?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60",
    ),
    (
        3,
        "Copa Frutos Rojos",
        "Especialidades",
        5200,
        "https://es.hellorecipes.net/thumb/768/helado-de-frutos-rojos-saludable.webp",
    ),
    (
        4,
        "Banana Split",
        "Especialidades",
        6500,
        "https://thumbs.dreamstime.com/b/banana-split-sundae-dessert-umbrella-48261592.jpg",
    ),
    (
        5,
        "Pote Familiar 1L",
        "Para Llevar",
        12900,
        "https://images.unsplash.com/photo-1501443762994-82bd5dace89a?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60",
    ),
    (
        6,
        "Cono Pistacho",
        "Conos Clásicos",
        4200,
        "https://thumbs.dreamstime.com/b/una-bola-de-helado-pistacho-en-un-cono-waffle-rodeada-pistachos-crujientes-sobre-superficie-verde-brillante-imagen-creada-con-420490286.jpg",
    ),
    (
        7,
        "Envase 500ml Chocolate",
        "Para Llevar",
        7900,
        "https://img.magnific.com/fotos-premium/tres-cucharadas-helado-chocolate-taza-marron_1077802-451766.jpg?semt=ais_hybrid&w=740&q=80",
    ),
]

PERSONAL = [
    ("USR-ADMIN", "admin@frionatural.cl", ["admin"]),
    ("USR-DUENO", "dueno@frionatural.cl", ["dueno"]),
    ("USR-CAJERO", "cajero@frionatural.cl", ["cajero"]),
    ("USR-DESPACHO", "despacho@frionatural.cl", ["despacho"]),
]

CLIENTES = [
    (
        "CLI-ANA",
        "11111111-1",
        "Ana Pérez Soto",
        "ana@correo.cl",
        "Av. Pajaritos 1234",
        "Maipú",
    ),
    (
        "CLI-PEDRO",
        "22222222-2",
        "Pedro González Rojas",
        "pedro@correo.cl",
        "Los Pinos 456",
        "Maipú",
    ),
]


def crear_indices(m: MongoClient):
    m.fn_auth.users.create_index("email", unique=True)
    m.fn_auth.users.create_index("user_id", unique=True)
    m.fn_auth.sessions.create_index("token_hash", unique=True)
    m.fn_auth.sessions.create_index("expires_at", expireAfterSeconds=0)
    m.fn_inventory.products.create_index("id", unique=True)
    m.fn_inventory.reservations.create_index("order_id", unique=True)
    m.fn_clients.clients.create_index("user_id", unique=True)
    m.fn_clients.clients.create_index("run", unique=True)
    m.fn_clients.clients.create_index("correo", unique=True)
    m.fn_orders.orders.create_index("id", unique=True)
    m.fn_orders.orders.create_index([("user_id", ASCENDING), ("creado", ASCENDING)])
    m.fn_orders.orders.create_index([("estado", ASCENDING), ("pagado_en", ASCENDING)])
    m.fn_orders.receipts.create_index("order_id", unique=True)
    m.fn_orders.events.create_index("seq", unique=True)
    m.fn_analytics.sales.create_index("order_id", unique=True)
    m.fn_analytics.sales.create_index(
        [("anulado", ASCENDING), ("pagado_en", ASCENDING)]
    )
    m.fn_payments.payments.create_index("id", unique=True)
    m.fn_payments.payments.create_index("provider_ref", unique=True)
    m.fn_payments.payments.create_index("order_id")
    m.fn_payments.payments.create_index(
        [("order_id", ASCENDING), ("estado", ASCENDING)],
        unique=True,
        partialFilterExpression={"estado": "PENDIENTE"},
    )
    m.fn_payments.webhook_events.create_index("event_id", unique=True)


def cargar_datos(m: MongoClient):
    if m.fn_inventory.products.count_documents({}) == 0:
        m.fn_inventory.products.insert_many(
            [
                {
                    "id": i,
                    "nombre": n,
                    "categoria": c,
                    "precio": p,
                    "imagen": img,
                    "descripcion": f"{n} artesanal",
                    "disponible": True,
                    "stock": 50,
                }
                for i, n, c, p, img in PRODUCTOS
            ]
        )
    if m.fn_auth.users.count_documents({}) == 0:
        cuentas = PERSONAL + [
            (uid, correo, ["cliente"]) for uid, _, _, correo, _, _ in CLIENTES
        ]
        m.fn_auth.users.insert_many(
            [
                {
                    "user_id": uid,
                    "email": correo,
                    "password_hash": hash_clave(CLAVE_DEMO),
                    "roles": roles,
                    "activo": True,
                    "email_verificado": True,
                }
                for uid, correo, roles in cuentas
            ]
        )
    if m.fn_clients.clients.count_documents({}) == 0:
        m.fn_clients.clients.insert_many(
            [
                {
                    "user_id": uid,
                    "run": run,
                    "nombreCompleto": nombre,
                    "correo": correo,
                    "direccion": dir_,
                    "comuna": comuna,
                    "provincia": "Santiago",
                    "region": "Metropolitana",
                    "fechaNacimiento": "1995-05-10",
                    "sexo": "Prefiero no decirlo",
                    "telefono": "+56 9 1234 5678",
                    "email_verificado": True,
                    "activo": True,
                    "creado": datetime.now(timezone.utc),
                }
                for uid, run, nombre, correo, dir_, comuna in CLIENTES
            ]
        )


if __name__ == "__main__":
    mongo = MongoClient(MONGODB_URI)
    if "--reset" in sys.argv:
        for nombre in [
            "fn_auth",
            "fn_inventory",
            "fn_clients",
            "fn_orders",
            "fn_payments",
            "fn_analytics",
        ]:
            mongo.drop_database(nombre)
    crear_indices(mongo)
    cargar_datos(mongo)
    print("Base de datos lista")
