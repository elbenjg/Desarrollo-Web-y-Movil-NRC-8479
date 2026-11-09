# Sistema orders: pedidos, ciclo de vida, anulación y boletas.
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Header, Query
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from pymongo.errors import PyMongoError

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

SECRETO = requerir_env("ORDERS_SECRET")
INVENTORY_SECRET = requerir_env("INVENTORY_SECRET")
CLIENTS_SECRET = requerir_env("CLIENTS_SECRET")

db = AsyncIOMotorClient(MONGODB_URI, tz_aware=True)["fn_orders"]
pedidos = db["orders"]
boletas = db["receipts"]
contadores = db["counters"]
eventos = db["events"]
log = logging.getLogger("orders")
REINTENTO_LIBERAR_S = 5


async def reintentar_liberaciones():
    while True:
        await asyncio.sleep(REINTENTO_LIBERAR_S)
        try:
            async for doc in pedidos.find({"stock_por_liberar": True}, {"id": 1}):
                resp = await llamar(
                    "inventory",
                    "POST",
                    f"/internal/release/{doc['id']}",
                    INVENTORY_SECRET,
                )
                if resp.status_code == 200:
                    await pedidos.update_one(
                        {"id": doc["id"]}, {"$unset": {"stock_por_liberar": ""}}
                    )
        except PyMongoError:
            log.warning("no se pudieron revisar las liberaciones pendientes")


@asynccontextmanager
async def ciclo(app):
    from orders.grpc_server import iniciar_servidor

    servidor = await iniciar_servidor(eventos)
    tarea = asyncio.create_task(reintentar_liberaciones())
    yield
    tarea.cancel()
    await servidor.stop(2)


def verificar_secreto(x_internal_secret: str = Header(default="")):
    if not iguales(x_internal_secret, SECRETO):
        raise HTTPException(status_code=403, detail="Solicitud no autorizada")


app = FastAPI(
    title="Orders Service",
    lifespan=ciclo,
    dependencies=[Depends(verificar_secreto)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
instalar_logs(app, "orders")

ESTADOS_VENDIDOS = ["PAGADO", "EN_PREPARACION", "DESPACHADO", "ENTREGADO"]
TRANSICIONES = {
    "PAGADO": "EN_PREPARACION",
    "EN_PREPARACION": "DESPACHADO",
    "DESPACHADO": "ENTREGADO",
}
IVA = 0.19


class ItemIn(BaseModel):
    product_id: int
    cantidad: int = Field(gt=0, le=50)


class EnvioIn(BaseModel):
    direccion: str = Field(min_length=1, max_length=150)
    comuna: str = Field(min_length=1, max_length=60)
    provincia: str = Field(min_length=1, max_length=60)
    region: str = Field(min_length=1, max_length=60)


class PedidoIn(BaseModel):
    items: List[ItemIn] = Field(min_length=1, max_length=20)
    envio: EnvioIn


class AnulacionIn(BaseModel):
    motivo: str = Field(min_length=5, max_length=300)


class EstadoIn(BaseModel):
    estado: Literal["EN_PREPARACION", "DESPACHADO", "ENTREGADO"]


class PagoConfirmadoIn(BaseModel):
    payment_id: str
    monto: int


def ahora():
    return datetime.now(timezone.utc)


async def siguiente(nombre: str) -> int:
    doc = await contadores.find_one_and_update(
        {"_id": nombre},
        {"$inc": {"valor": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return doc["valor"]


async def publicar(doc: dict):
    await eventos.insert_one(
        {
            "seq": await siguiente("events"),
            "order_id": doc["id"],
            "estado": doc["estado"],
            "fecha": ahora(),
            "total": doc["total"],
            "items": [
                {k: i[k] for k in ("product_id", "nombre", "cantidad", "subtotal")}
                for i in doc["items"]
            ],
        }
    )


def pedido_dto(doc: dict, ident: dict) -> dict:
    dto = {k: doc[k] for k in ["id", "estado", "items", "total", "creado", "historial"]}
    dto["motivo_anulacion"] = doc.get("motivo_anulacion")
    if doc["user_id"] == ident["user_id"] or {"admin", "despacho"} & set(
        ident["roles"]
    ):
        dto["envio"] = doc["envio"]
    if es_staff(ident):
        dto["user_id"] = doc["user_id"]
    return dto


async def pedido_autorizado(order_id: str, ident: dict) -> dict:
    requerir_sesion(ident)
    doc = await pedidos.find_one({"id": order_id})
    if not doc or (doc["user_id"] != ident["user_id"] and not es_staff(ident)):
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return doc


@app.get("/health")
def health():
    return {"status": "ok", "service": "orders"}


@app.post("/orders", status_code=201)
async def crear(pedido: PedidoIn, ident: dict = Depends(identidad)):
    requerir_roles(ident, "cliente")
    cantidades = {}
    for item in pedido.items:
        cantidades[item.product_id] = cantidades.get(item.product_id, 0) + item.cantidad
    order_id = f"PED-{await siguiente('orders'):06d}"
    resp = await llamar(
        "inventory",
        "POST",
        "/internal/reserve",
        INVENTORY_SECRET,
        json={
            "order_id": order_id,
            "items": [{"product_id": p, "cantidad": c} for p, c in cantidades.items()],
        },
    )
    if resp.status_code == 409:
        raise HTTPException(status_code=409, detail=resp.json()["detail"])
    if resp.status_code != 200:
        raise HTTPException(
            status_code=503, detail="No fue posible reservar el stock, reintenta"
        )
    items = [
        {**l, "subtotal": l["precio_unitario"] * l["cantidad"]}
        for l in resp.json()["items"]
    ]
    doc = {
        "id": order_id,
        "user_id": ident["user_id"],
        "items": items,
        "total": sum(i["subtotal"] for i in items),
        "envio": pedido.envio.model_dump(),
        "estado": "PENDIENTE_PAGO",
        "creado": ahora(),
        "historial": [
            {"estado": "PENDIENTE_PAGO", "fecha": ahora(), "por": ident["user_id"]}
        ],
    }
    try:
        await pedidos.insert_one(doc)
    except Exception:
        await llamar(
            "inventory", "POST", f"/internal/release/{order_id}", INVENTORY_SECRET
        )
        raise
    await publicar(doc)
    return pedido_dto(doc, ident)


@app.get("/orders")
async def listar(
    estado: Optional[str] = Query(None, max_length=20),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    ident: dict = Depends(identidad),
):
    requerir_sesion(ident)
    filtro = {} if es_staff(ident) else {"user_id": ident["user_id"]}
    if estado:
        filtro["estado"] = estado
    orden = 1 if "despacho" in ident["roles"] else -1
    total = await pedidos.count_documents(filtro)
    docs = (
        await pedidos.find(filtro)
        .sort("creado", orden)
        .skip(skip)
        .limit(limit)
        .to_list(limit)
    )
    return {"total": total, "pedidos": [pedido_dto(d, ident) for d in docs]}


@app.get("/orders/{order_id}")
async def obtener(order_id: str, ident: dict = Depends(identidad)):
    return pedido_dto(await pedido_autorizado(order_id, ident), ident)


@app.post("/orders/{order_id}/cancel")
async def anular(
    order_id: str, anulacion: AnulacionIn, ident: dict = Depends(identidad)
):
    doc = await pedido_autorizado(order_id, ident)
    if "admin" in ident["roles"]:
        permitidos = ["PENDIENTE_PAGO", "PAGADO", "EN_PREPARACION"]
    elif doc["user_id"] == ident["user_id"]:
        permitidos = [
            "PENDIENTE_PAGO",
            "PAGADO",
        ]
    else:
        raise HTTPException(
            status_code=403, detail="Rol sin permiso para anular pedidos"
        )
    actualizado = await pedidos.find_one_and_update(
        {"id": order_id, "estado": {"$in": permitidos}},
        {
            "$set": {
                "estado": "ANULADO",
                "motivo_anulacion": anulacion.motivo,
                "reembolso_pendiente": doc["estado"] != "PENDIENTE_PAGO",
            },
            "$push": {
                "historial": {
                    "estado": "ANULADO",
                    "fecha": ahora(),
                    "por": ident["user_id"],
                    "motivo": anulacion.motivo,
                }
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    if not actualizado:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede anular un pedido en estado {doc['estado']}",
        )
    await publicar(actualizado)
    resp = await llamar(
        "inventory", "POST", f"/internal/release/{order_id}", INVENTORY_SECRET
    )
    if resp.status_code != 200:
        await pedidos.update_one(
            {"id": order_id}, {"$set": {"stock_por_liberar": True}}
        )
    return pedido_dto(actualizado, ident)


@app.patch("/orders/{order_id}/status")
async def cambiar_estado(
    order_id: str, cambio: EstadoIn, ident: dict = Depends(identidad)
):
    requerir_roles(ident, "despacho", "admin")
    doc = await pedido_autorizado(order_id, ident)
    if TRANSICIONES.get(doc["estado"]) != cambio.estado:
        raise HTTPException(
            status_code=409,
            detail=f"Transición inválida: {doc['estado']} -> {cambio.estado}",
        )
    actualizado = await pedidos.find_one_and_update(
        {"id": order_id, "estado": doc["estado"]},
        {
            "$set": {"estado": cambio.estado},
            "$push": {
                "historial": {
                    "estado": cambio.estado,
                    "fecha": ahora(),
                    "por": ident["user_id"],
                }
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    if not actualizado:
        raise HTTPException(
            status_code=409, detail="El pedido cambió de estado, vuelve a consultarlo"
        )
    await publicar(actualizado)
    return pedido_dto(actualizado, ident)


@app.post("/orders/{order_id}/receipt", status_code=201)
async def emitir_boleta(order_id: str, ident: dict = Depends(identidad)):
    requerir_roles(ident, "cajero", "admin")
    doc = await pedido_autorizado(order_id, ident)
    if doc["estado"] not in ESTADOS_VENDIDOS:
        raise HTTPException(
            status_code=409, detail="Solo se emite boleta de pedidos pagados"
        )
    boleta = await boletas.find_one({"order_id": order_id}, {"_id": 0})
    if not boleta:
        neto = round(doc["total"] / (1 + IVA))
        boleta = {
            "numero": await siguiente("receipts"),
            "order_id": order_id,
            "user_id": doc["user_id"],
            "items": doc["items"],
            "neto": neto,
            "iva": doc["total"] - neto,
            "total": doc["total"],
            "fecha": ahora(),
            "emitida_por": ident["user_id"],
            "enviada": False,
        }
        await boletas.insert_one(dict(boleta))
    if boleta["enviada"]:
        return boleta
    detalle = "\n".join(
        f"{i['nombre']} x{i['cantidad']}: ${i['subtotal']}" for i in doc["items"]
    )
    resp = await llamar(
        "clients",
        "POST",
        "/internal/notify",
        CLIENTS_SECRET,
        json={
            "user_id": doc["user_id"],
            "asunto": f"Boleta N°{boleta['numero']} - Frío Natural",
            "cuerpo": f"Pedido {order_id}\n{detalle}\nNeto: ${boleta['neto']}\nIVA: ${boleta['iva']}\nTotal: ${doc['total']}",
        },
    )
    boleta["enviada"] = resp.status_code == 200
    await boletas.update_one(
        {"order_id": order_id}, {"$set": {"enviada": boleta["enviada"]}}
    )
    return boleta


@app.get("/orders/{order_id}/receipt")
async def ver_boleta(order_id: str, ident: dict = Depends(identidad)):
    await pedido_autorizado(order_id, ident)
    boleta = await boletas.find_one({"order_id": order_id}, {"_id": 0})
    if not boleta:
        raise HTTPException(status_code=404, detail="El pedido aún no tiene boleta")
    return boleta


@app.post("/internal/orders/{order_id}/paid")
async def marcar_pagado(order_id: str, pago: PagoConfirmadoIn):
    doc = await pedidos.find_one({"id": order_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if doc.get("payment_id") == pago.payment_id:
        return {
            "id": order_id,
            "estado": doc["estado"],
        }
    if pago.monto != doc["total"]:
        raise HTTPException(
            status_code=409,
            detail="El monto pagado no coincide con el total del pedido",
        )
    actualizado = await pedidos.find_one_and_update(
        {"id": order_id, "estado": "PENDIENTE_PAGO"},
        {
            "$set": {
                "estado": "PAGADO",
                "payment_id": pago.payment_id,
                "pagado_en": ahora(),
            },
            "$push": {
                "historial": {"estado": "PAGADO", "fecha": ahora(), "por": "payments"}
            },
        },
        return_document=ReturnDocument.AFTER,
    )
    if not actualizado:
        raise HTTPException(
            status_code=409, detail=f"El pedido está {doc['estado']} y no admite pago"
        )
    await publicar(actualizado)
    return {"id": order_id, "estado": "PAGADO"}
