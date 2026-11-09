# Utilidades compartidas por los microservicios privados de Frío Natural.
import contextvars
import hashlib
import logging
import os
import re
import secrets
import time
import uuid
from pathlib import Path

import grpc
import httpx
from fastapi import Header, HTTPException, Request

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

URLS = {
    "auth": os.getenv("AUTH_URL", "http://127.0.0.1:8100"),
    "inventory": os.getenv("INVENTORY_URL", "http://127.0.0.1:8001"),
    "orders": os.getenv("ORDERS_URL", "http://127.0.0.1:8002"),
    "clients": os.getenv("CLIENTS_URL", "http://127.0.0.1:8003"),
    "payments": os.getenv("PAYMENTS_URL", "http://127.0.0.1:8004"),
    "graphql": os.getenv("GRAPHQL_URL", "http://127.0.0.1:8005"),
    "analytics": os.getenv("ANALYTICS_URL", "http://127.0.0.1:8006"),
}

PATRON_CORREO = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"

ROLES_STAFF = {"admin", "dueno", "cajero", "despacho"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
correlacion = contextvars.ContextVar("correlacion", default="-")
cliente_http = httpx.AsyncClient(timeout=5.0)


def canal_orders_grpc():
    ca = Path(requerir_env("GRPC_TLS_CA")).read_bytes()
    return grpc.aio.secure_channel(
        os.getenv("ORDERS_GRPC_ADDR", "127.0.0.1:50051"),
        grpc.ssl_channel_credentials(ca),
        options=[("grpc.max_receive_message_length", 1024 * 1024)],
    )


def requerir_env(nombre: str) -> str:
    valor = os.getenv(nombre)
    if not valor:
        raise RuntimeError(f"{nombre} no está configurado")
    return valor


def iguales(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode(), b.encode())


def hash_clave(clave: str) -> str:
    sal = secrets.token_bytes(16)
    digest = hashlib.scrypt(clave.encode(), salt=sal, n=2**14, r=8, p=1)
    return f"scrypt${sal.hex()}${digest.hex()}"


def verificar_clave(clave: str, guardado: str) -> bool:
    _, sal, digest = guardado.split("$")
    calculado = hashlib.scrypt(
        clave.encode(), salt=bytes.fromhex(sal), n=2**14, r=8, p=1
    )
    return iguales(calculado.hex(), digest)


def identidad(
    x_user_id: str = Header(default=""), x_user_roles: str = Header(default="")
) -> dict:
    return {
        "user_id": x_user_id or None,
        "roles": [r for r in x_user_roles.split(",") if r],
    }


def requerir_sesion(ident: dict):
    if not ident["user_id"]:
        raise HTTPException(status_code=401, detail="Sesión requerida")


def requerir_roles(ident: dict, *roles: str):
    requerir_sesion(ident)
    if not set(roles) & set(ident["roles"]):
        raise HTTPException(
            status_code=403, detail="Rol sin permiso para esta operación"
        )


def es_staff(ident: dict) -> bool:
    return bool(ROLES_STAFF & set(ident["roles"]))


async def llamar(
    servicio: str,
    metodo: str,
    ruta: str,
    secreto: str,
    ident: dict | None = None,
    **kwargs,
):
    headers = {"X-Internal-Secret": secreto, "X-Correlation-Id": correlacion.get()}
    if ident:
        headers["X-User-Id"] = ident["user_id"] or ""
        headers["X-User-Roles"] = ",".join(ident["roles"])
    try:
        return await cliente_http.request(
            metodo, URLS[servicio] + ruta, headers=headers, **kwargs
        )
    except httpx.RequestError:
        return httpx.Response(503)


def instalar_logs(app, nombre: str):
    log = logging.getLogger(nombre)

    @app.middleware("http")
    async def registrar(request: Request, call_next):
        cid = request.headers.get("x-correlation-id", "")
        if not re.fullmatch(r"[A-Za-z0-9-]{8,64}", cid):
            cid = uuid.uuid4().hex
        correlacion.set(cid)
        inicio = time.perf_counter()
        respuesta = await call_next(request)
        log.info(
            "cid=%s %s %s -> %s (%.1f ms)",
            cid,
            request.method,
            request.url.path,
            respuesta.status_code,
            (time.perf_counter() - inicio) * 1000,
        )
        respuesta.headers["X-Correlation-Id"] = cid
        return respuesta
