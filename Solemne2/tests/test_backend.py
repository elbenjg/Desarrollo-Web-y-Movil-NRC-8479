# Pruebas de integración contra el backend en ejecución (iniciado a mano o con scripts\iniciar.ps1 -Reset).
# Uso: py -m pytest tests -v
import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import grpc
import httpx
import psutil
import pytest
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import seguimiento_pb2 as pb
import seguimiento_pb2_grpc as pb_grpc

GW = "http://127.0.0.1:8000/api/v1"
RAIZ = Path(__file__).resolve().parents[1]
RUNTIME = RAIZ / ".runtime"
CLAVE = "Demo1234"
ANUAL = {"desde": time.strftime("%Y-01-01"), "hasta": time.strftime("%Y-12-31")}
ENVIO = {
    "direccion": "Av. Pajaritos 1234",
    "comuna": "Maipú",
    "provincia": "Santiago",
    "region": "Metropolitana",
}

mongo = MongoClient("mongodb://localhost:27017")


class EsperaLimite(httpx.HTTPTransport):
    def handle_request(self, request):
        r = super().handle_request(request)
        if r.status_code == 429 and not request.url.path.endswith("/auth/login"):
            r.close()
            time.sleep(61)
            r = super().handle_request(request)
        return r


http = httpx.Client(timeout=15, transport=EsperaLimite())
_tokens = {}


def vault(ruta: str) -> dict:
    archivo = RUNTIME / "vault-token"
    token = (
        archivo.read_text()
        if archivo.exists()
        else os.environ.get("VAULT_TOKEN", "dev-only-token")
    )
    r = httpx.get(f"http://127.0.0.1:8200/v1/{ruta}", headers={"X-Vault-Token": token})
    return r.json()["data"]["data"]


def token(email: str) -> str:
    if email not in _tokens:
        r = http.post(f"{GW}/auth/login", json={"email": email, "password": CLAVE})
        assert r.status_code == 200, r.text
        _tokens[email] = r.json()["access_token"]
    return _tokens[email]


def h(email: str) -> dict:
    return {"Authorization": f"Bearer {token(email)}"}


ANA, PEDRO = "ana@correo.cl", "pedro@correo.cl"
ADMIN, DUENO, CAJERO, DESPACHO = (
    "admin@frionatural.cl",
    "dueno@frionatural.cl",
    "cajero@frionatural.cl",
    "despacho@frionatural.cl",
)


def stock(product_id: int) -> int:
    return http.get(f"{GW}/products/{product_id}", headers=h(ADMIN)).json()["stock"]


def crear_pedido(email=ANA, items=None):
    r = http.post(
        f"{GW}/orders",
        headers=h(email),
        json={
            "items": items
            or [{"product_id": 1, "cantidad": 2}, {"product_id": 3, "cantidad": 1}],
            "envio": ENVIO,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def aviso_firmado(provider_ref: str, monto: int, estado="APROBADO", event_id=None):
    cuerpo = json.dumps(
        {
            "event_id": event_id or uuid.uuid4().hex,
            "provider_ref": provider_ref,
            "estado": estado,
            "monto": monto,
        }
    ).encode()
    firma = hmac.new(
        vault("secret/data/payments")["provider_webhook_secret"].encode(),
        cuerpo,
        hashlib.sha256,
    ).hexdigest()
    return http.post(
        f"{GW}/payments/webhook",
        content=cuerpo,
        headers={"Content-Type": "application/json", "X-Provider-Signature": firma},
    )


def reporte_hoy() -> dict:
    hoy = time.strftime("%Y-%m-%d")
    return http.get(
        f"{GW}/reports/sales", headers=h(DUENO), params={"desde": hoy, "hasta": hoy}
    ).json()


def esperar_analytics(plazo_s=5.0):
    ultimo = mongo.fn_orders.events.find_one(sort=[("seq", -1)])["seq"]
    limite = time.monotonic() + plazo_s
    while (mongo.fn_analytics.checkpoint.find_one({"_id": "orders"}) or {}).get(
        "seq", 0
    ) < ultimo:
        assert (
            time.monotonic() < limite
        ), "analytics no se puso al día dentro del retraso aceptado"
        time.sleep(0.1)


def pedido_pagado(email=ANA):
    pedido = crear_pedido(email)
    pago = http.post(
        f"{GW}/payments",
        headers=h(email),
        json={"order_id": pedido["id"], "metodo": "Webpay"},
    ).json()
    assert (
        aviso_firmado(pago["provider_ref"], pago["monto"]).json()["estado"]
        == "APROBADO"
    )
    return pedido, pago


def test_catalogo_anonimo_solo_campos_publicos():
    r = http.get(f"{GW}/products", params={"available": "true"})
    assert r.status_code == 200
    productos = r.json()
    assert len(productos) == 7
    assert set(productos[0]) == {
        "id",
        "nombre",
        "categoria",
        "precio",
        "imagen",
        "descripcion",
        "disponible",
    }


def test_catalogo_filtro_invalido():
    assert http.get(f"{GW}/products", params={"available": "quizas"}).status_code == 422


def test_admin_ve_stock_y_mantiene_productos():
    r = http.post(
        f"{GW}/products",
        headers=h(ADMIN),
        json={
            "nombre": "Cono Menta",
            "categoria": "Conos Clásicos",
            "precio": 3900,
            "stock": 10,
        },
    )
    assert r.status_code == 201 and r.json()["stock"] == 10
    pid = r.json()["id"]
    r = http.patch(
        f"{GW}/products/{pid}/availability",
        headers=h(DUENO),
        json={"disponible": False},
    )
    assert r.status_code == 200 and r.json()["disponible"] is False
    assert http.delete(f"{GW}/products/{pid}", headers=h(ADMIN)).status_code == 204
    assert http.get(f"{GW}/products/{pid}").status_code == 404


def test_operacion_protegida_sin_sesion():
    assert (
        http.post(
            f"{GW}/orders",
            json={"items": [{"product_id": 1, "cantidad": 1}], "envio": ENVIO},
        ).status_code
        == 401
    )
    r = http.get(f"{GW}/orders", headers={"Authorization": "Bearer token-falso"})
    assert r.status_code == 401


def test_admin_desde_rol_sin_permiso():
    assert http.delete(f"{GW}/products/1", headers=h(ANA)).status_code == 403
    assert (
        http.get(
            f"{GW}/reports/sales",
            headers=h(CAJERO),
            params=ANUAL,
        ).status_code
        == 403
    )
    assert http.get(f"{GW}/admin/users", headers=h(DUENO)).status_code == 403


def test_ruta_no_publicada():
    assert http.get(f"{GW}/internal/reserve").status_code == 404
    assert http.get(f"{GW}/products/a!b").status_code == 404
    assert http.get(f"{GW}/products/1/extra").status_code == 404
    assert http.delete(f"{GW}/orders/PED-000001", headers=h(ADMIN)).status_code == 405


def test_cabeceras_de_identidad_falsas_se_descartan():
    falsas = {**h(ANA), "X-User-Id": "USR-ADMIN", "X-User-Roles": "admin,dueno"}
    r = http.get(
        f"{GW}/reports/sales",
        headers=falsas,
        params=ANUAL,
    )
    assert r.status_code == 403


def test_acceso_directo_a_servicios_privados_rechazado():
    for puerto, ruta in [
        (8001, "/products"),
        (8002, "/orders"),
        (8003, "/clients"),
        (8004, "/payments?order_id=x"),
        (8100, "/users"),
    ]:
        r = httpx.get(
            f"http://127.0.0.1:{puerto}{ruta}",
            headers={"X-User-Id": "USR-ADMIN", "X-User-Roles": "admin"},
        )
        assert r.status_code == 403, (puerto, r.text)
    r = httpx.post(
        "http://127.0.0.1:8005/graphql",
        json={"query": "{ pedidos { total } }"},
        headers={"X-User-Id": "USR-ADMIN", "X-User-Roles": "admin"},
    )
    assert r.status_code == 403
    for puerto in (8000, 8001, 8002, 8003, 8004, 8006, 8100):
        for ruta in ("/docs", "/redoc", "/openapi.json"):
            r = httpx.get(f"http://127.0.0.1:{puerto}{ruta}")
            assert r.status_code in (403, 404), (puerto, ruta)


def test_pedido_ajeno_no_se_entrega():
    pedido = crear_pedido(ANA)
    assert http.get(f"{GW}/orders/{pedido['id']}", headers=h(ANA)).status_code == 200
    r = http.get(f"{GW}/orders/{pedido['id']}", headers=h(PEDRO))
    assert r.status_code == 404 and "items" not in r.text
    assert all(
        p["id"] != pedido["id"]
        for p in http.get(f"{GW}/orders", headers=h(PEDRO)).json()["pedidos"]
    )
    r = http.get(f"{GW}/orders/{pedido['id']}", headers=h(CAJERO))
    assert r.status_code == 200 and "envio" not in r.json()


def test_registro_verificacion_y_perfil():
    correo = f"cliente{uuid.uuid4().hex[:6]}@correo.cl"
    datos = {
        "nombreCompleto": "Camila Rojas",
        "run": "12.345.678-5",
        "direccion": "Calle 1",
        "comuna": "Maipú",
        "provincia": "Santiago",
        "region": "Metropolitana",
        "fechaNacimiento": "2000-01-15",
        "sexo": "Femenino",
        "correo": correo,
        "telefono": "+56 9 8765 4321",
        "clave": "secreta123",
    }
    assert (
        http.post(f"{GW}/clients", json={**datos, "run": "12.345.678-9"}).status_code
        == 422
    )
    previo = mongo.fn_clients.clients.find_one({"run": "12345678-5"})
    if previo:
        mongo.fn_auth.users.delete_one({"user_id": previo["user_id"]})
        mongo.fn_auth.sessions.delete_many({"user_id": previo["user_id"]})
        mongo.fn_clients.outbox.delete_many({"para": previo["correo"]})
        mongo.fn_clients.clients.delete_one({"run": "12345678-5"})
    r = http.post(f"{GW}/clients", json=datos)
    assert r.status_code == 201 and "clave" not in r.text
    assert http.post(f"{GW}/clients", json=datos).status_code == 409
    login = http.post(
        f"{GW}/auth/login", json={"email": correo, "password": "secreta123"}
    )
    assert login.status_code == 403
    correo_enviado = mongo.fn_clients.outbox.find_one({"para": correo})
    codigo = re.search(r"[\w-]{20,}", correo_enviado["cuerpo"]).group()
    assert (
        http.post(f"{GW}/clients/verify-email", json={"token": codigo}).status_code
        == 200
    )
    login = http.post(
        f"{GW}/auth/login", json={"email": correo, "password": "secreta123"}
    )
    assert login.status_code == 200
    auth = {"Authorization": f"Bearer {login.json()['access_token']}"}
    perfil = http.get(f"{GW}/clients/me", headers=auth).json()
    assert perfil["run"] == "12345678-5" and "password" not in json.dumps(perfil)
    hash_guardado = mongo.fn_auth.users.find_one({"email": correo})["password_hash"]
    assert hash_guardado.startswith("scrypt$") and "secreta123" not in hash_guardado


def test_login_no_revela_si_el_correo_existe():
    a = http.post(
        f"{GW}/auth/login", json={"email": "noexiste@correo.cl", "password": "x"}
    )
    b = http.post(f"{GW}/auth/login", json={"email": ANA, "password": "incorrecta"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_precio_y_total_los_calcula_el_servidor():
    r = http.post(
        f"{GW}/orders",
        headers=h(ANA),
        json={
            "items": [{"product_id": 1, "cantidad": 2, "precio": 1}],
            "total": 1,
            "envio": ENVIO,
        },
    )
    assert r.status_code == 201
    assert r.json()["total"] == 2 * 3500 and r.json()["estado"] == "PENDIENTE_PAGO"


def test_stock_se_reserva_y_se_recupera_al_anular():
    antes = stock(4)
    pedido = crear_pedido(ANA, [{"product_id": 4, "cantidad": 3}])
    assert stock(4) == antes - 3
    r = http.post(
        f"{GW}/orders/{pedido['id']}/cancel",
        headers=h(ANA),
        json={"motivo": "Me equivoqué de sabor"},
    )
    assert r.status_code == 200 and r.json()["estado"] == "ANULADO"
    assert stock(4) == antes
    assert (
        mongo.fn_orders.orders.find_one({"id": pedido["id"]})["motivo_anulacion"]
        == "Me equivoqué de sabor"
    )
    assert (
        http.post(
            f"{GW}/orders/{pedido['id']}/cancel",
            headers=h(ANA),
            json={"motivo": "otra vez"},
        ).status_code
        == 409
    )
    assert stock(4) == antes


def test_sin_stock_no_descuenta_parcialmente():
    antes1, antes5 = stock(1), stock(5)
    r = http.post(
        f"{GW}/orders",
        headers=h(ANA),
        json={
            "items": [
                {"product_id": 1, "cantidad": 1},
                {"product_id": 5, "cantidad": 50},
                {"product_id": 5, "cantidad": 50},
            ],
            "envio": ENVIO,
        },
    )
    assert r.status_code == 409
    assert (stock(1), stock(5)) == (antes1, antes5)


def test_pago_no_se_confirma_con_datos_del_frontend():
    pedido = crear_pedido(ANA)
    r = http.post(
        f"{GW}/payments",
        headers=h(ANA),
        json={
            "order_id": pedido["id"],
            "metodo": "Webpay",
            "monto": 1,
            "estado": "APROBADO",
        },
    )
    assert (
        r.status_code == 201
        and r.json()["monto"] == pedido["total"]
        and r.json()["estado"] == "PENDIENTE"
    )
    assert (
        http.patch(
            f"{GW}/orders/{pedido['id']}/status",
            headers=h(ANA),
            json={"estado": "PAGADO"},
        ).status_code
        == 403
    )
    cuerpo = json.dumps(
        {
            "event_id": "x1",
            "provider_ref": r.json()["provider_ref"],
            "estado": "APROBADO",
            "monto": pedido["total"],
        }
    )
    sin_firma = http.post(
        f"{GW}/payments/webhook",
        content=cuerpo,
        headers={"Content-Type": "application/json"},
    )
    firma_falsa = http.post(
        f"{GW}/payments/webhook",
        content=cuerpo,
        headers={"Content-Type": "application/json", "X-Provider-Signature": "0" * 64},
    )
    assert sin_firma.status_code == firma_falsa.status_code == 401
    assert (
        http.get(f"{GW}/orders/{pedido['id']}", headers=h(ANA)).json()["estado"]
        == "PENDIENTE_PAGO"
    )


def test_reintentar_pago_devuelve_el_mismo_con_su_checkout():
    pedido = crear_pedido(ANA)
    datos = {"order_id": pedido["id"], "metodo": "Webpay"}
    primero = http.post(f"{GW}/payments", headers=h(ANA), json=datos).json()
    segundo = http.post(f"{GW}/payments", headers=h(ANA), json=datos).json()
    assert segundo["id"] == primero["id"]
    assert segundo["checkout_url"] == primero["checkout_url"]


def test_pagos_simultaneos_crean_un_solo_cobro():
    pedido = crear_pedido(ANA)
    encabezados = h(ANA)

    def pagar(_):
        return http.post(
            f"{GW}/payments",
            headers=encabezados,
            json={"order_id": pedido["id"], "metodo": "Webpay"},
        ).json()["id"]

    with ThreadPoolExecutor(12) as hilos:
        assert len(set(hilos.map(pagar, range(12)))) == 1
    assert mongo.fn_payments.payments.count_documents({"order_id": pedido["id"]}) == 1


def test_aviso_firmado_mal_formado_responde_400():
    cuerpo = b"[]"
    firma = hmac.new(
        vault("secret/data/payments")["provider_webhook_secret"].encode(),
        cuerpo,
        hashlib.sha256,
    ).hexdigest()
    r = http.post(
        f"{GW}/payments/webhook",
        content=cuerpo,
        headers={"X-Provider-Signature": firma},
    )
    assert r.status_code == 400


def test_fechas_del_pedido_indican_zona_horaria():
    pedido = crear_pedido(ANA)
    leido = http.get(f"{GW}/orders/{pedido['id']}", headers=h(ANA)).json()
    assert leido["creado"].endswith(("+00:00", "Z")), leido["creado"]
    assert pedido["creado"].endswith(("+00:00", "Z")), pedido["creado"]


def test_pago_de_otro_cliente_rechazado():
    pedido = crear_pedido(ANA)
    r = http.post(
        f"{GW}/payments",
        headers=h(PEDRO),
        json={"order_id": pedido["id"], "metodo": "Onepay"},
    )
    assert r.status_code == 404


def test_aviso_con_monto_alterado_se_rechaza():
    pedido = crear_pedido(ANA)
    pago = http.post(
        f"{GW}/payments",
        headers=h(ANA),
        json={"order_id": pedido["id"], "metodo": "Webpay"},
    ).json()
    assert aviso_firmado(pago["provider_ref"], 1).json()["estado"] == "RECHAZADO"
    assert (
        http.get(f"{GW}/orders/{pedido['id']}", headers=h(ANA)).json()["estado"]
        == "PENDIENTE_PAGO"
    )


def test_pago_duplicado_se_procesa_una_vez():
    pedido = crear_pedido(ANA)
    pago = http.post(
        f"{GW}/payments",
        headers=h(ANA),
        json={"order_id": pedido["id"], "metodo": "Webpay"},
    ).json()
    reintento = http.post(
        f"{GW}/payments",
        headers=h(ANA),
        json={"order_id": pedido["id"], "metodo": "Webpay"},
    ).json()
    assert reintento["id"] == pago["id"]
    evento = uuid.uuid4().hex
    assert (
        aviso_firmado(pago["provider_ref"], pago["monto"], event_id=evento).json()[
            "estado"
        ]
        == "APROBADO"
    )
    assert (
        aviso_firmado(pago["provider_ref"], pago["monto"], event_id=evento).json()[
            "duplicado"
        ]
        is True
    )
    doc = mongo.fn_orders.orders.find_one({"id": pedido["id"]})
    assert (
        doc["estado"] == "PAGADO"
        and [e["estado"] for e in doc["historial"]].count("PAGADO") == 1
    )


def test_ciclo_de_despacho_boleta_y_reporte():
    pedido, pago = pedido_pagado(ANA)
    pid = pedido["id"]
    pagados = {"estado": "PAGADO", "limit": 100}
    total = http.get(f"{GW}/orders", headers=h(DESPACHO), params=pagados).json()[
        "total"
    ]
    cola = http.get(
        f"{GW}/orders",
        headers=h(DESPACHO),
        params={**pagados, "skip": max(total - 100, 0)},
    ).json()["pedidos"]
    assert pid in [p["id"] for p in cola]
    assert [p["creado"] for p in cola] == sorted(
        p["creado"] for p in cola
    ) and "envio" in cola[0]
    assert (
        http.patch(
            f"{GW}/orders/{pid}/status",
            headers=h(DESPACHO),
            json={"estado": "ENTREGADO"},
        ).status_code
        == 409
    )
    for estado in ["EN_PREPARACION", "DESPACHADO", "ENTREGADO"]:
        r = http.patch(
            f"{GW}/orders/{pid}/status", headers=h(DESPACHO), json={"estado": estado}
        )
        assert r.status_code == 200 and r.json()["estado"] == estado
    assert http.post(f"{GW}/orders/{pid}/receipt", headers=h(ANA)).status_code == 403
    boleta = http.post(f"{GW}/orders/{pid}/receipt", headers=h(CAJERO)).json()
    assert (
        boleta["total"] == pedido["total"]
        and boleta["neto"] + boleta["iva"] == boleta["total"]
        and boleta["enviada"]
    )
    assert (
        http.post(f"{GW}/orders/{pid}/receipt", headers=h(CAJERO)).json()["numero"]
        == boleta["numero"]
    )
    assert mongo.fn_clients.outbox.find_one(
        {"para": ANA, "asunto": {"$regex": f"N°{boleta['numero']} "}}
    )
    assert http.get(f"{GW}/orders/{pid}/receipt", headers=h(ANA)).status_code == 200
    assert http.get(f"{GW}/orders/{pid}/receipt", headers=h(PEDRO)).status_code == 404
    assert (
        http.post(
            f"{GW}/orders/{pid}/cancel", headers=h(ANA), json={"motivo": "tarde"}
        ).status_code
        == 409
    )
    esperar_analytics()
    reporte = reporte_hoy()
    assert (
        reporte["total_ventas"] >= pedido["total"] and reporte["cantidad_pedidos"] >= 1
    )


def test_mantenedor_de_usuarios_y_clientes():
    r = http.post(
        f"{GW}/admin/users",
        headers=h(ADMIN),
        json={
            "email": f"cajero{uuid.uuid4().hex[:5]}@frionatural.cl",
            "password": "Cajero123",
            "roles": ["cajero"],
        },
    )
    assert r.status_code == 201 and "password" not in json.dumps(r.json())
    uid = r.json()["user_id"]
    assert (
        http.put(
            f"{GW}/admin/users/{uid}",
            headers=h(ADMIN),
            json={"roles": ["cajero"], "activo": False},
        ).status_code
        == 200
    )
    assert (
        http.post(
            f"{GW}/admin/users",
            headers=h(ANA),
            json={"email": "yo@correo.cl", "password": "123456", "roles": ["admin"]},
        ).status_code
        == 403
    )
    assert http.get(f"{GW}/clients", headers=h(ADMIN)).status_code == 200
    assert http.get(f"{GW}/clients", headers=h(ANA)).status_code == 403


def gql(email, query, variables=None):
    return http.post(
        f"{GW}/graphql",
        headers=h(email),
        json={"query": query, "variables": variables or {}},
    )


RESUMEN = """query($id: ID!) { resumenPedido(id: $id) {
    id estado total items { nombre cantidad subtotal producto { categoria disponible } }
    pagos { estado monto } envio { comuna } } }"""


def test_graphql_agrega_orders_inventory_y_payments():
    pedido, pago = pedido_pagado(ANA)
    r = gql(ANA, RESUMEN, {"id": pedido["id"]})
    datos = r.json()
    assert "errors" not in datos, datos
    resumen = datos["data"]["resumenPedido"]
    assert resumen["estado"] == "PAGADO" and resumen["pagos"][0]["estado"] == "APROBADO"
    assert resumen["items"][0]["producto"]["categoria"] == "Conos Clásicos"
    assert resumen["envio"]["comuna"] == "Maipú"


def test_graphql_autorizacion_por_recurso_y_campo():
    pedido_pagado(PEDRO)
    esperar_analytics()
    pedido = crear_pedido(ANA)
    assert (
        gql(PEDRO, RESUMEN, {"id": pedido["id"]}).json()["data"]["resumenPedido"]
        is None
    )
    r = gql(CAJERO, RESUMEN, {"id": pedido["id"]}).json()
    assert (
        r["data"]["resumenPedido"]["envio"] is None
        and r["errors"][0]["path"][-1] == "envio"
    )
    r = gql(ANA, "{ pedidos { pedidos { clienteId } } }").json()
    assert any(e["extensions"]["code"] == "FORBIDDEN" for e in r["errors"])
    r = gql(
        ANA,
        f'{{ reporteVentas(desde: "{ANUAL["desde"]}", hasta: "{ANUAL["hasta"]}") {{ totalVentas }} }}',
    ).json()
    assert r["errors"][0]["extensions"]["code"] == "FORBIDDEN"
    r = gql(
        DUENO,
        f'{{ reporteVentas(desde: "{ANUAL["desde"]}", hasta: "{ANUAL["hasta"]}") {{ totalVentas porProducto {{ nombre categoria }} }} }}',
    ).json()
    assert "errors" not in r and r["data"]["reporteVentas"]["totalVentas"] > 0


def test_graphql_limites():
    assert (
        "errors"
        not in gql(ANA, "{ pedidos { pedidos { items { producto { id } } } } }").json()
    )
    profunda = gql(
        ANA, "{ pedidos { pedidos { items { producto { id { x } } } } } }"
    ).json()
    assert any("profunda" in e["message"] for e in profunda["errors"])
    alias = "{ " + " ".join(f"a{i}: pedidos {{ total }}" for i in range(80)) + " }"
    assert "costosa" in gql(ANA, alias).json()["errors"][0]["message"]
    assert (
        "porPagina"
        in gql(ANA, "{ pedidos(porPagina: 500) { total } }").json()["errors"][0][
            "message"
        ]
    )
    assert "errors" in gql(ANA, "{ __schema { types { name } } }").json()
    assert (
        http.post(f"{GW}/graphql", json={"query": "{ pedidos { total } }"}).status_code
        == 401
    )


def test_graphql_abusos_responden_controlado():
    ciclo = "{ ...A } fragment A on Query { ...B } fragment B on Query { ...A }"
    assert gql(ANA, ciclo).status_code == 400
    niveles = "".join(
        f"fragment F{i} on Query {{ {f'...F{i + 1} ' * 9} }} " for i in range(9)
    )
    bomba = "{ ...F0 } " + niveles + "fragment F9 on Query { pedidos { total } }"
    respuesta = gql(ANA, bomba)
    assert respuesta.status_code == 400 and respuesta.elapsed.total_seconds() < 3
    assert "costosa" in respuesta.text
    lote = http.post(
        f"{GW}/graphql", headers=h(ANA), json=[{"query": "{ pedidos { total } }"}] * 5
    )
    assert lote.status_code == 400 and '"pedidos"' not in lote.text
    for cuerpo, codigo in [
        (b"{malo", 400),
        (b'{"query":"' + b" " * 20000 + b'"}', 413),
    ]:
        r = http.post(
            f"{GW}/graphql",
            headers={**h(ANA), "Content-Type": "application/json"},
            content=cuerpo,
        )
        assert r.status_code == codigo and r.json()["detail"], r.text
        assert "node_modules" not in r.text and "UNIVERSIDAD" not in r.text
    malo = gql(DUENO, '{ reporteVentas(desde: "malo", hasta: "x") { totalVentas } }')
    assert malo.json()["errors"][0]["extensions"]["code"] == "BAD_USER_INPUT"


def test_cuerpo_demasiado_grande_se_corta_aunque_no_declare_tamano():
    def partes():
        for _ in range(10):
            yield b"x" * 10_000

    r = http.post(f"{GW}/auth/login", content=partes())
    assert r.status_code == 413


def test_logout_revoca_el_token():
    login = http.post(
        f"{GW}/auth/login", json={"email": PEDRO, "password": CLAVE}
    ).json()
    auth = {"Authorization": f"Bearer {login['access_token']}"}
    assert http.get(f"{GW}/orders", headers=auth).status_code == 200
    assert http.post(f"{GW}/auth/logout", headers=auth).status_code == 200
    assert http.get(f"{GW}/orders", headers=auth).status_code == 401


def canal_grpc():
    return grpc.secure_channel(
        "127.0.0.1:50051",
        grpc.ssl_channel_credentials((RUNTIME / "tls" / "orders.crt").read_bytes()),
    )


def credencial(consumidor: str):
    secreto = (
        vault("secret/data/gateway")["grpc_gateway"]
        if consumidor == "gateway"
        else vault("secret/data/analytics")["grpc_analytics"]
    )
    return [("x-internal-secret", secreto)]


def codigo_grpc(llamada) -> grpc.StatusCode:
    try:
        llamada()
    except grpc.RpcError as e:
        return e.code()
    return grpc.StatusCode.OK


def test_grpc_autenticacion_tls_y_autorizacion_por_metodo():
    crear_pedido(ANA)
    with canal_grpc() as canal:
        stub = pb_grpc.SeguimientoStub(canal)
        ultimo = lambda md: stub.UltimoSeq(
            pb.UltimoSeqRequest(), metadata=md, timeout=3
        )
        assert codigo_grpc(lambda: ultimo([])) == grpc.StatusCode.UNAUTHENTICATED
        assert (
            codigo_grpc(lambda: ultimo([("x-internal-secret", "falso")]))
            == grpc.StatusCode.UNAUTHENTICATED
        )
        assert (
            codigo_grpc(lambda: ultimo(credencial("analytics")))
            == grpc.StatusCode.PERMISSION_DENIED
        )
        assert ultimo(credencial("gateway")).seq > 0
        negativo = lambda: list(
            stub.SeguirEventos(
                pb.SeguirRequest(desde_seq=-1),
                metadata=credencial("analytics"),
                timeout=3,
            )
        )
        assert codigo_grpc(negativo) == grpc.StatusCode.INVALID_ARGUMENT
    with grpc.insecure_channel("127.0.0.1:50051") as canal:
        llamada = lambda: pb_grpc.SeguimientoStub(canal).UltimoSeq(
            pb.UltimoSeqRequest(), metadata=credencial("gateway"), timeout=3
        )
        assert codigo_grpc(llamada) == grpc.StatusCode.UNAVAILABLE


def test_grpc_stream_reconecta_sin_duplicar_ni_perder():
    crear_pedido(ANA)
    crear_pedido(ANA)
    md = credencial("analytics")
    with canal_grpc() as canal:
        stub = pb_grpc.SeguimientoStub(canal)
        total = stub.UltimoSeq(
            pb.UltimoSeqRequest(), metadata=credencial("gateway"), timeout=3
        ).seq
        mitad, recibidos = total // 2, []
        stream = stub.SeguirEventos(
            pb.SeguirRequest(desde_seq=0), metadata=md, timeout=10
        )
        for ev in stream:
            recibidos.append(ev.seq)
            if ev.seq == mitad:
                stream.cancel()
                break
        stream = stub.SeguirEventos(
            pb.SeguirRequest(desde_seq=recibidos[-1]), metadata=md, timeout=10
        )
        for ev in stream:
            recibidos.append(ev.seq)
            if ev.seq >= total:
                stream.cancel()
                break
    assert recibidos == list(range(1, total + 1))
    ev = mongo.fn_orders.events.find_one({"seq": total})
    assert "user_id" not in ev and "envio" not in ev


def test_analytics_privado_sin_datos_personales_y_excluye_anulados():
    secretos = vault("secret/data/gateway")
    assert httpx.get("http://127.0.0.1:8006/reports/sales").status_code == 403
    assert (
        httpx.get(
            "http://127.0.0.1:8006/health",
            headers={"X-Internal-Secret": secretos["orders"]},
        ).status_code
        == 403
    )
    antes = reporte_hoy()["total_ventas"]
    pedido, _ = pedido_pagado(PEDRO)
    esperar_analytics()
    reporte = reporte_hoy()
    assert (
        reporte["total_ventas"] == antes + pedido["total"]
        and reporte["actualizado_hasta_seq"] > 0
    )
    venta = mongo.fn_analytics.sales.find_one({"order_id": pedido["id"]})
    assert set(venta) <= {"_id", "order_id", "pagado_en", "total", "anulado", "items"}
    assert (
        http.post(
            f"{GW}/orders/{pedido['id']}/cancel",
            headers=h(PEDRO),
            json={"motivo": "me equivoqué de sabor"},
        ).status_code
        == 200
    )
    esperar_analytics()
    assert reporte_hoy()["total_ventas"] == antes


def leer_evento_sse(headers: dict) -> dict:
    with http.stream("GET", f"{GW}/dispatch/events", headers=headers, timeout=10) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith(
            "text/event-stream"
        )
        evento = {}
        for linea in r.iter_lines():
            if linea.startswith("id: "):
                evento["id"] = int(linea[4:])
            elif linea.startswith("data: "):
                evento["data"] = json.loads(linea[6:])
                return evento


def test_sse_despacho_recibe_eventos_y_reanuda_con_last_event_id():
    assert http.get(f"{GW}/dispatch/events", headers=h(ANA)).status_code == 403
    assert http.get(f"{GW}/dispatch/events").status_code == 401
    assert (
        http.get(
            f"{GW}/dispatch/events", headers={**h(DESPACHO), "Last-Event-ID": "abc"}
        ).status_code
        == 400
    )
    enorme = {**h(DESPACHO), "Last-Event-ID": "9" * 30}
    assert http.get(f"{GW}/dispatch/events", headers=enorme).status_code == 400
    pedido = crear_pedido(ANA)
    seq = mongo.fn_orders.events.find_one({"order_id": pedido["id"]})["seq"]
    evento = leer_evento_sse({**h(DESPACHO), "Last-Event-ID": str(seq - 1)})
    assert evento["id"] == seq and evento["data"]["order_id"] == pedido["id"]
    assert (
        evento["data"]["estado"] == "PENDIENTE_PAGO" and "envio" not in evento["data"]
    )


requiere_script = pytest.mark.skipif(
    not (RUNTIME / "pids.txt").exists(),
    reason="detiene servicios: ejecutar con scripts\\iniciar.ps1",
)


def detener_servicio(puerto: int):
    for conexion in psutil.net_connections(kind="tcp"):
        if conexion.status == psutil.CONN_LISTEN and conexion.laddr.port == puerto:
            psutil.Process(conexion.pid).kill()
            return
    pytest.fail(f"No hay ningún servicio escuchando en el puerto {puerto}")


def reiniciar_servicio(nombre: str, modulo: str, puerto: int, secreto: str, env: dict):
    with open(RUNTIME / f"{nombre}.log", "a") as log:
        proceso = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                f"{modulo}:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(puerto),
                "--no-access-log",
            ],
            cwd=RAIZ / "backend",
            env={**os.environ, **env},
            stdout=subprocess.DEVNULL,
            stderr=log,
        )
    pids = [
        pid
        for pid in (RUNTIME / "pids.txt").read_text().split()
        if psutil.pid_exists(int(pid))
    ]
    (RUNTIME / "pids.txt").write_text("\n".join(pids + [str(proceso.pid)]))
    for _ in range(40):
        try:
            salud = httpx.get(
                f"http://127.0.0.1:{puerto}/health",
                headers={"X-Internal-Secret": secreto},
            )
            if salud.status_code == 200:
                return
        except httpx.RequestError:
            pass
        time.sleep(0.5)
    pytest.exit(f"{nombre} no volvió a iniciar: revisar .runtime\\{nombre}.log", 1)


@requiere_script
def test_inventory_caido_responde_controlado_y_graphql_parcial():
    pedido = crear_pedido(ANA)
    detener_servicio(8001)
    try:
        r = http.post(
            f"{GW}/orders",
            headers=h(ANA),
            json={"items": [{"product_id": 1, "cantidad": 1}], "envio": ENVIO},
        )
        assert r.status_code == 503
        assert http.get(f"{GW}/products").status_code == 502
        datos = gql(ANA, RESUMEN, {"id": pedido["id"]}).json()
        assert datos["data"]["resumenPedido"]["total"] == pedido["total"]
        assert datos["data"]["resumenPedido"]["items"][0]["producto"] is None
        assert datos["errors"][0]["extensions"]["code"] == "SERVICE_UNAVAILABLE"
    finally:
        secreto = vault("secret/data/gateway")["inventory"]
        reiniciar_servicio(
            "inventory", "inventory.main", 8001, secreto, {"INVENTORY_SECRET": secreto}
        )
    assert http.get(f"{GW}/products").status_code == 200


@requiere_script
def test_analytics_caido_se_pone_al_dia_sin_contar_dos_veces():
    detener_servicio(8006)
    try:
        assert (
            http.get(f"{GW}/reports/sales", headers=h(DUENO), params=ANUAL).status_code
            == 502
        )
        antes = mongo.fn_analytics.sales.count_documents({})
        pedido, _ = pedido_pagado(ANA)
    finally:
        secreto = vault("secret/data/gateway")["analytics"]
        reiniciar_servicio(
            "analytics",
            "analytics.main",
            8006,
            secreto,
            {
                "ANALYTICS_SECRET": secreto,
                "GRPC_ANALYTICS_SECRET": vault("secret/data/analytics")[
                    "grpc_analytics"
                ],
                "GRPC_TLS_CA": str(RUNTIME / "tls" / "orders.crt"),
            },
        )
    esperar_analytics()
    assert mongo.fn_analytics.sales.count_documents({}) == antes + 1
    assert mongo.fn_analytics.sales.count_documents({"order_id": pedido["id"]}) == 1


def reiniciar(nombre: str):
    gw = vault("secret/data/gateway")
    tls = RUNTIME / "tls"
    modulo, puerto, env = {
        "auth": ("auth_service.main", 8100, {"AUTH_SECRET": gw["auth"]}),
        "inventory": ("inventory.main", 8001, {"INVENTORY_SECRET": gw["inventory"]}),
        "clients": (
            "clients.main",
            8003,
            {"CLIENTS_SECRET": gw["clients"], "AUTH_SECRET": gw["auth"]},
        ),
        "orders": (
            "orders.main",
            8002,
            {
                "ORDERS_SECRET": gw["orders"],
                "INVENTORY_SECRET": gw["inventory"],
                "CLIENTS_SECRET": gw["clients"],
                "GRPC_GATEWAY_SECRET": gw["grpc_gateway"],
                "GRPC_ANALYTICS_SECRET": vault("secret/data/analytics")[
                    "grpc_analytics"
                ],
                "GRPC_TLS_CERT": str(tls / "orders.crt"),
                "GRPC_TLS_KEY": str(tls / "orders.key"),
            },
        ),
    }[nombre]
    reiniciar_servicio(nombre, modulo, puerto, gw[nombre], env)


@requiere_script
def test_aviso_con_orders_caido_se_puede_reintentar():
    pedido = crear_pedido(ANA)
    pago = http.post(
        f"{GW}/payments",
        headers=h(ANA),
        json={"order_id": pedido["id"], "metodo": "Webpay"},
    ).json()
    evento = uuid.uuid4().hex
    detener_servicio(8002)
    try:
        r = aviso_firmado(pago["provider_ref"], pago["monto"], event_id=evento)
        assert r.status_code == 503
    finally:
        reiniciar("orders")
    r = aviso_firmado(pago["provider_ref"], pago["monto"], event_id=evento)
    assert r.json()["estado"] == "APROBADO", r.text
    leido = http.get(f"{GW}/orders/{pedido['id']}", headers=h(ANA)).json()
    assert leido["estado"] == "PAGADO"


@requiere_script
def test_anular_con_inventory_caido_devuelve_el_stock_al_volver():
    antes = stock(2)
    pedido = crear_pedido(ANA, [{"product_id": 2, "cantidad": 3}])
    detener_servicio(8001)
    try:
        r = http.post(
            f"{GW}/orders/{pedido['id']}/cancel",
            headers=h(ANA),
            json={"motivo": "inventory estaba caído"},
        )
        assert r.status_code == 200 and r.json()["estado"] == "ANULADO"
    finally:
        reiniciar("inventory")
    for _ in range(30):
        if stock(2) == antes:
            break
        time.sleep(0.5)
    assert stock(2) == antes
    doc = mongo.fn_orders.orders.find_one({"id": pedido["id"]})
    assert "stock_por_liberar" not in doc


@requiere_script
def test_boleta_con_clients_caido_queda_sin_enviar_y_se_reintenta():
    pedido, _ = pedido_pagado(ANA)
    url = f"{GW}/orders/{pedido['id']}/receipt"
    detener_servicio(8003)
    try:
        primera = http.post(url, headers=h(CAJERO))
        assert primera.status_code == 201 and primera.json()["enviada"] is False
    finally:
        reiniciar("clients")
    segunda = http.post(url, headers=h(CAJERO)).json()
    assert segunda["enviada"] is True and segunda["numero"] == primera.json()["numero"]


@requiere_script
def test_registro_con_auth_caido_no_deja_perfil_huerfano():
    correo = "caida@correo.cl"
    mongo.fn_clients.clients.delete_many({"correo": correo})
    mongo.fn_auth.users.delete_many({"email": correo})
    datos = {
        "nombreCompleto": "Prueba Caida",
        "run": "9.876.543-3",
        "direccion": "Calle 1",
        "comuna": "Maipú",
        "provincia": "Santiago",
        "region": "Metropolitana",
        "fechaNacimiento": "2000-01-15",
        "sexo": "Femenino",
        "correo": correo,
        "telefono": "+56 9 8765 4321",
        "clave": "secreta123",
    }
    detener_servicio(8100)
    try:
        assert http.post(f"{GW}/clients", json=datos).status_code == 503
        assert mongo.fn_clients.clients.count_documents({"correo": correo}) == 0
    finally:
        reiniciar("auth")
    assert http.post(f"{GW}/clients", json=datos).status_code == 201


def test_limite_de_solicitudes_en_login():
    codigos = [
        http.post(
            f"{GW}/auth/login", json={"email": ANA, "password": "mala"}
        ).status_code
        for _ in range(25)
    ]
    assert 429 in codigos
