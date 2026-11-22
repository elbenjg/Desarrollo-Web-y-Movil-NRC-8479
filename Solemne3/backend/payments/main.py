# Sistema payments: inicio de pagos y verificación del aviso firmado del proveedor.
import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Header, Query, Request
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from comun import (
    MONGODB_URI,
    es_staff,
    identidad,
    instalar_logs,
    llamar,
    requerir_env,
    requerir_roles,
    requerir_sesion,
    iguales,
)

SECRETO = requerir_env("PAYMENTS_SECRET")
ORDERS_SECRET = requerir_env("ORDERS_SECRET")
PROVIDER_WEBHOOK_SECRET = requerir_env("PROVIDER_WEBHOOK_SECRET")

db = AsyncIOMotorClient(MONGODB_URI, tz_aware=True)["fn_payments"]
pagos = db["payments"]
eventos = db["webhook_events"]


def verificar_secreto(x_internal_secret: str = Header(default="")):
    if not iguales(x_internal_secret, SECRETO):
        raise HTTPException(status_code=403, detail="Solicitud no autorizada")


app = FastAPI(
    title="Payments Service",
    dependencies=[Depends(verificar_secreto)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
instalar_logs(app, "payments")


class PagoIn(BaseModel):
    order_id: str = Field(min_length=1, max_length=40)
    metodo: Literal["Webpay", "Onepay", "Transferencia bancaria"]


class AvisoProveedor(BaseModel):
    event_id: str = Field(min_length=1, max_length=80)
    provider_ref: str = Field(min_length=1, max_length=80)
    estado: Literal["APROBADO", "RECHAZADO"]
    monto: int


def pago_dto(doc: dict) -> dict:
    return {
        k: doc.get(k)
        for k in [
            "id",
            "order_id",
            "monto",
            "metodo",
            "estado",
            "provider_ref",
            "creado",
        ]
    }


def pago_con_checkout(doc: dict) -> dict:
    return {
        **pago_dto(doc),
        "checkout_url": f"https://sandbox.proveedor.example/pay/{doc['provider_ref']}",
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "payments"}


@app.post("/payments", status_code=201)
async def iniciar(pago: PagoIn, ident: dict = Depends(identidad)):
    requerir_roles(ident, "cliente")
    resp = await llamar(
        "orders", "GET", f"/orders/{pago.order_id}", ORDERS_SECRET, ident=ident
    )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if resp.status_code != 200:
        raise HTTPException(
            status_code=503, detail="No fue posible consultar el pedido"
        )
    pedido = resp.json()
    if pedido["estado"] != "PENDIENTE_PAGO":
        raise HTTPException(
            status_code=409, detail="El pedido no está pendiente de pago"
        )
    previo = await pagos.find_one({"order_id": pago.order_id, "estado": "PENDIENTE"})
    if previo:
        return pago_con_checkout(previo)
    doc = {
        "id": "PAG-" + secrets.token_hex(5).upper(),
        "order_id": pago.order_id,
        "user_id": ident["user_id"],
        "monto": pedido["total"],
        "metodo": pago.metodo,
        "estado": "PENDIENTE",
        "provider_ref": "SBX-" + secrets.token_hex(8),
        "creado": datetime.now(timezone.utc),
    }
    try:
        await pagos.insert_one(doc)
    except DuplicateKeyError:
        doc = await pagos.find_one({"order_id": pago.order_id, "estado": "PENDIENTE"})
    return pago_con_checkout(doc)


@app.get("/payments")
async def listar(
    order_id: str = Query(..., max_length=40), ident: dict = Depends(identidad)
):
    requerir_sesion(ident)
    filtro = {"order_id": order_id}
    if not es_staff(ident):
        filtro["user_id"] = ident["user_id"]
    return [
        pago_dto(d) for d in await pagos.find(filtro).sort("creado", -1).to_list(20)
    ]


@app.get("/payments/{payment_id}")
async def obtener(payment_id: str, ident: dict = Depends(identidad)):
    requerir_sesion(ident)
    doc = await pagos.find_one({"id": payment_id})
    if not doc or (doc["user_id"] != ident["user_id"] and not es_staff(ident)):
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    return pago_dto(doc)


@app.post("/webhook")
async def aviso_proveedor(
    request: Request, x_provider_signature: str = Header(default="")
):
    cuerpo = await request.body()
    esperada = hmac.new(
        PROVIDER_WEBHOOK_SECRET.encode(), cuerpo, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(x_provider_signature.encode(), esperada.encode()):
        raise HTTPException(status_code=401, detail="Firma inválida")
    try:
        aviso = AvisoProveedor.model_validate_json(cuerpo)
    except ValueError:
        raise HTTPException(status_code=400, detail="Aviso mal formado")
    try:
        await eventos.insert_one(
            {"event_id": aviso.event_id, "fecha": datetime.now(timezone.utc)}
        )
    except DuplicateKeyError:
        return {"procesado": False, "duplicado": True}
    pago = await pagos.find_one({"provider_ref": aviso.provider_ref})
    if not pago or pago["estado"] != "PENDIENTE":
        return {"procesado": False, "motivo": "pago inexistente o ya resuelto"}
    if aviso.estado == "RECHAZADO" or aviso.monto != pago["monto"]:
        await pagos.update_one({"id": pago["id"]}, {"$set": {"estado": "RECHAZADO"}})
        return {"procesado": True, "estado": "RECHAZADO"}
    resp = await llamar(
        "orders",
        "POST",
        f"/internal/orders/{pago['order_id']}/paid",
        ORDERS_SECRET,
        json={"payment_id": pago["id"], "monto": pago["monto"]},
    )
    if resp.status_code == 409:
        await pagos.update_one(
            {"id": pago["id"]}, {"$set": {"estado": "REQUIERE_REEMBOLSO"}}
        )
        return {"procesado": True, "estado": "REQUIERE_REEMBOLSO"}
    if resp.status_code != 200:
        await eventos.delete_one({"event_id": aviso.event_id})
        raise HTTPException(
            status_code=503, detail="No fue posible confirmar el pedido, reintente"
        )
    await pagos.update_one({"id": pago["id"]}, {"$set": {"estado": "APROBADO"}})
    return {"procesado": True, "estado": "APROBADO"}
