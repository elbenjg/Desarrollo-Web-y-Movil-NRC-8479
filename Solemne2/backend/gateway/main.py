# API Gateway público de Frío Natural.
import json
import os
import re
import time
from collections import defaultdict, deque

import grpc
import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

import seguimiento_pb2 as pb
import seguimiento_pb2_grpc as pb_grpc
from comun import (
    URLS,
    canal_orders_grpc,
    cliente_http,
    correlacion,
    instalar_logs,
    requerir_env,
)

VAULT_ADDR = os.getenv("VAULT_ADDR", "http://127.0.0.1:8200")
VAULT_TOKEN = requerir_env("VAULT_TOKEN")
MAX_BODY = 64 * 1024

app = FastAPI(
    title="Frío Natural - API Gateway",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
instalar_logs(app, "gateway")

ANONIMO, SESION = "anonimo", "sesion"

RUTAS = [
    ("S01", "GET", "/api/v1/products", "inventory", "/products", ANONIMO),
    ("S02", "GET", "/api/v1/products/{id}", "inventory", "/products/{id}", ANONIMO),
    ("S03", "POST", "/api/v1/products", "inventory", "/products", ("admin",)),
    ("S04", "PUT", "/api/v1/products/{id}", "inventory", "/products/{id}", ("admin",)),
    (
        "S05",
        "PATCH",
        "/api/v1/products/{id}/availability",
        "inventory",
        "/products/{id}/availability",
        ("admin", "dueno"),
    ),
    (
        "S06",
        "DELETE",
        "/api/v1/products/{id}",
        "inventory",
        "/products/{id}",
        ("admin",),
    ),
    ("S07", "POST", "/api/v1/auth/login", "auth", "/login", ANONIMO),
    ("S08", "POST", "/api/v1/auth/logout", "auth", "/logout", SESION),
    ("S09", "POST", "/api/v1/clients", "clients", "/clients", ANONIMO),
    (
        "S10",
        "POST",
        "/api/v1/clients/verify-email",
        "clients",
        "/clients/verify-email",
        ANONIMO,
    ),
    ("S11", "GET", "/api/v1/clients/me", "clients", "/clients/me", ("cliente",)),
    ("S12", "PUT", "/api/v1/clients/me", "clients", "/clients/me", ("cliente",)),
    ("S13", "GET", "/api/v1/clients", "clients", "/clients", ("admin",)),
    ("S14", "GET", "/api/v1/clients/{id}", "clients", "/clients/{id}", ("admin",)),
    ("S15", "PUT", "/api/v1/clients/{id}", "clients", "/clients/{id}", ("admin",)),
    ("S16", "DELETE", "/api/v1/clients/{id}", "clients", "/clients/{id}", ("admin",)),
    ("S17", "POST", "/api/v1/contact", "clients", "/contact", ANONIMO),
    ("S18", "POST", "/api/v1/orders", "orders", "/orders", ("cliente",)),
    ("S19", "GET", "/api/v1/orders", "orders", "/orders", SESION),
    ("S20", "GET", "/api/v1/orders/{id}", "orders", "/orders/{id}", SESION),
    (
        "S21",
        "POST",
        "/api/v1/orders/{id}/cancel",
        "orders",
        "/orders/{id}/cancel",
        ("cliente", "admin"),
    ),
    (
        "S22",
        "PATCH",
        "/api/v1/orders/{id}/status",
        "orders",
        "/orders/{id}/status",
        ("despacho", "admin"),
    ),
    (
        "S23",
        "POST",
        "/api/v1/orders/{id}/receipt",
        "orders",
        "/orders/{id}/receipt",
        ("cajero", "admin"),
    ),
    (
        "S24",
        "GET",
        "/api/v1/orders/{id}/receipt",
        "orders",
        "/orders/{id}/receipt",
        SESION,
    ),
    (
        "S25",
        "GET",
        "/api/v1/reports/sales",
        "analytics",
        "/reports/sales",
        ("dueno", "admin"),
    ),
    ("S26", "POST", "/api/v1/payments", "payments", "/payments", ("cliente",)),
    ("S27", "GET", "/api/v1/payments/{id}", "payments", "/payments/{id}", SESION),
    ("S28", "POST", "/api/v1/payments/webhook", "payments", "/webhook", ANONIMO),
    ("S29", "GET", "/api/v1/admin/users", "auth", "/users", ("admin",)),
    ("S30", "POST", "/api/v1/admin/users", "auth", "/users", ("admin",)),
    ("S31", "PUT", "/api/v1/admin/users/{id}", "auth", "/users/{id}", ("admin",)),
    ("S32", "POST", "/api/v1/graphql", "graphql", "/graphql", SESION),
    (
        "S33",
        "GET",
        "/api/v1/dispatch/events",
        "orders-grpc",
        "SeguirEventos",
        ("despacho", "admin"),
    ),
]
ID_VALIDO = re.compile(r"[A-Za-z0-9_-]{1,40}")

LIMITES = {"S07": 20, "S09": 10}
LIMITE_GENERAL = int(os.getenv("GATEWAY_RATE_LIMIT", "120"))
ventanas = defaultdict(deque)

_cache_secretos = {"valor": None, "expira": 0.0}

SSE_DURACION_S = 300
MAX_SSE = 20
_grpc = {"canal": None, "abiertos": 0}


def limitar(ip: str, sid: str):
    clave = (ip, sid if sid in LIMITES else "*")
    maximo = LIMITES.get(sid, LIMITE_GENERAL)
    ventana = ventanas[clave]
    ahora = time.monotonic()
    while ventana and ahora - ventana[0] > 60:
        ventana.popleft()
    if len(ventana) >= maximo:
        raise HTTPException(
            status_code=429, detail="Demasiadas solicitudes, intenta en un minuto"
        )
    ventana.append(ahora)


async def obtener_secretos() -> dict:
    if _cache_secretos["valor"] and time.monotonic() < _cache_secretos["expira"]:
        return _cache_secretos["valor"]
    try:
        response = await cliente_http.get(
            f"{VAULT_ADDR}/v1/secret/data/gateway",
            timeout=3.0,
            headers={"X-Vault-Token": VAULT_TOKEN},
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503, detail="Servicio temporalmente no disponible"
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=503, detail="Servicio temporalmente no disponible"
        )
    _cache_secretos.update(
        valor=response.json()["data"]["data"], expira=time.monotonic() + 60
    )
    return _cache_secretos["valor"]


async def autenticar(token: str, secretos: dict) -> dict:
    try:
        response = await cliente_http.post(
            f"{URLS['auth']}/introspect",
            json={"token": token},
            timeout=3.0,
            headers={"X-Internal-Secret": secretos["auth"]},
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503, detail="Authentication Service no disponible"
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=502, detail="Error consultando Authentication Service"
        )
    identity = response.json()
    if not identity.get("active"):
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
    return identity


def comparar_ruta(externa: str, path: str):
    partes_ruta = externa.split("/")
    partes_path = path.split("/")
    if len(partes_ruta) != len(partes_path):
        return None
    id_recurso = ""
    for parte_ruta, parte_path in zip(partes_ruta, partes_path):
        if parte_ruta == "{id}":
            if not ID_VALIDO.fullmatch(parte_path):
                return None
            id_recurso = parte_path
        elif parte_ruta != parte_path:
            return None
    return id_recurso


def buscar_ruta(metodo: str, path: str):
    ruta_existe = False
    for sid, verbo, externa, destino, interna, acceso in RUTAS:
        id_recurso = comparar_ruta(externa, path)
        if id_recurso is None:
            continue
        ruta_existe = True
        if verbo == metodo:
            return sid, destino, interna.replace("{id}", id_recurso), acceso
    if ruta_existe:
        raise HTTPException(status_code=405, detail="Método no permitido")
    raise HTTPException(status_code=404, detail="Ruta no encontrada")


def stub_orders():
    if _grpc["canal"] is None:
        _grpc["canal"] = canal_orders_grpc()
    return pb_grpc.SeguimientoStub(_grpc["canal"])


async def eventos_despacho(request: Request, secretos: dict):
    if _grpc["abiertos"] >= MAX_SSE:
        raise HTTPException(
            status_code=503, detail="Demasiadas conexiones de seguimiento abiertas"
        )
    metadata = [
        ("x-internal-secret", secretos["grpc_gateway"]),
        ("x-correlation-id", correlacion.get()),
    ]
    stub = stub_orders()
    ultimo = request.headers.get("last-event-id") or request.query_params.get(
        "desde", ""
    )
    try:
        desde = (
            int(ultimo)
            if ultimo
            else (
                await stub.UltimoSeq(
                    pb.UltimoSeqRequest(), metadata=metadata, timeout=3.0
                )
            ).seq
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Last-Event-ID inválido")
    except grpc.aio.AioRpcError:
        raise HTTPException(
            status_code=503, detail="Seguimiento de pedidos no disponible"
        )
    if not 0 <= desde < 2**63:
        raise HTTPException(status_code=400, detail="Last-Event-ID inválido")

    async def generar():
        _grpc["abiertos"] += 1
        stream = stub.SeguirEventos(
            pb.SeguirRequest(desde_seq=desde), metadata=metadata, timeout=SSE_DURACION_S
        )
        try:
            yield "retry: 3000\n\n"
            async for ev in stream:
                datos = {
                    "order_id": ev.order_id,
                    "estado": ev.estado,
                    "fecha": ev.fecha,
                    "total": ev.total,
                    "items": [
                        {"nombre": i.nombre, "cantidad": i.cantidad} for i in ev.items
                    ],
                }
                yield f"id: {ev.seq}\nevent: estado\ndata: {json.dumps(datos, ensure_ascii=False)}\n\n"
        except grpc.aio.AioRpcError as e:
            if e.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
                yield 'event: error\ndata: {"detail": "Seguimiento interrumpido, reconectando"}\n\n'
        finally:
            stream.cancel()
            _grpc["abiertos"] -= 1

    return StreamingResponse(
        generar(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Correlation-Id": correlacion.get()},
    )


@app.exception_handler(HTTPException)
async def errores_controlados(request: Request, exc: HTTPException):
    return JSONResponse(
        {"detail": exc.detail},
        status_code=exc.status_code,
        headers={"X-Correlation-Id": correlacion.get()},
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "gateway"}


@app.api_route("/api/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(request: Request):
    sid, destino, ruta_interna, acceso = buscar_ruta(request.method, request.url.path)
    limitar(request.client.host if request.client else "?", sid)

    body = b""
    async for parte in request.stream():
        body += parte
        if len(body) > MAX_BODY:
            raise HTTPException(status_code=413, detail="Cuerpo demasiado grande")

    secretos = await obtener_secretos()
    autorizacion = request.headers.get("authorization", "")
    token = (
        autorizacion[7:].strip() if autorizacion.lower().startswith("bearer ") else ""
    )
    identity = await autenticar(token, secretos) if token else None

    if acceso != ANONIMO:
        if identity is None:
            raise HTTPException(status_code=401, detail="Bearer token requerido")
        if acceso != SESION and not set(acceso) & set(identity["roles"]):
            raise HTTPException(
                status_code=403, detail="Rol sin permiso para esta operación"
            )

    if sid == "S33":
        return await eventos_despacho(request, secretos)

    headers = {
        "X-Internal-Secret": secretos[destino],
        "X-Correlation-Id": correlacion.get(),
    }
    if identity:
        headers["X-User-Id"] = identity["user_id"]
        headers["X-User-Roles"] = ",".join(identity["roles"])
    if request.headers.get("content-type"):
        headers["Content-Type"] = request.headers["content-type"]
    if sid == "S28" and request.headers.get("x-provider-signature"):
        headers["X-Provider-Signature"] = request.headers["x-provider-signature"]
    if sid == "S08":
        body = httpx.Request("POST", "/", json={"token": token}).content
        headers["Content-Type"] = "application/json"

    try:
        upstream = await cliente_http.request(
            request.method,
            URLS[destino] + ruta_interna,
            timeout=10.0,
            params=request.query_params,
            content=body,
            headers=headers,
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504, detail="El servicio tardó demasiado en responder"
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502, detail="Error al comunicarse con el servicio"
        )

    response_headers = {"X-Correlation-Id": headers["X-Correlation-Id"]}
    if "content-type" in upstream.headers:
        response_headers["content-type"] = upstream.headers["content-type"]
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
    )
