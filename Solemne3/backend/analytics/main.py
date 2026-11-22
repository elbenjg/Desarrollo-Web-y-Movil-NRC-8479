# Servicio privado de analítica: se alimenta del stream gRPC de orders y responde el reporte de ventas.
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import grpc
from fastapi import Depends, FastAPI, HTTPException, Header
from motor.motor_asyncio import AsyncIOMotorClient

import seguimiento_pb2 as pb
import seguimiento_pb2_grpc as pb_grpc
from comun import (
    MONGODB_URI,
    canal_orders_grpc,
    identidad,
    instalar_logs,
    requerir_env,
    requerir_roles,
    iguales,
)

SECRETO = requerir_env("ANALYTICS_SECRET")
GRPC_SECRETO = requerir_env("GRPC_ANALYTICS_SECRET")
DEADLINE_S = 60
RETRASO_ACEPTADO_S = 5
ZONA = ZoneInfo("America/Santiago")

db = AsyncIOMotorClient(MONGODB_URI)["fn_analytics"]
ventas = db["sales"]
checkpoint = db["checkpoint"]
log = logging.getLogger("analytics")
estado_consumidor = {"conectado": False}


async def aplicar(ev: pb.EventoPedido):
    if ev.estado == "PAGADO":
        await ventas.update_one(
            {"order_id": ev.order_id},
            {
                "$set": {
                    "pagado_en": datetime.fromisoformat(ev.fecha),
                    "total": ev.total,
                    "anulado": False,
                    "items": [
                        {
                            "product_id": i.product_id,
                            "nombre": i.nombre,
                            "cantidad": i.cantidad,
                            "subtotal": i.subtotal,
                        }
                        for i in ev.items
                    ],
                }
            },
            upsert=True,
        )
    elif ev.estado == "ANULADO":
        await ventas.update_one({"order_id": ev.order_id}, {"$set": {"anulado": True}})
    await checkpoint.update_one(
        {"_id": "orders"},
        {"$set": {"seq": ev.seq, "actualizado": datetime.now(timezone.utc)}},
        upsert=True,
    )


async def consumir():
    async with canal_orders_grpc() as canal:
        stub = pb_grpc.SeguimientoStub(canal)
        while True:
            desde = (await checkpoint.find_one({"_id": "orders"}) or {}).get("seq", 0)
            try:
                stream = stub.SeguirEventos(
                    pb.SeguirRequest(desde_seq=desde),
                    timeout=DEADLINE_S,
                    metadata=[("x-internal-secret", GRPC_SECRETO)],
                )
                estado_consumidor["conectado"] = True
                async for ev in stream:
                    await aplicar(ev)
            except grpc.aio.AioRpcError as e:
                if e.code() != grpc.StatusCode.DEADLINE_EXCEEDED:
                    log.warning("stream de orders interrumpido: %s", e.code().name)
                    estado_consumidor["conectado"] = False
                    await asyncio.sleep(1)
            except Exception:
                log.exception("error aplicando eventos")
                estado_consumidor["conectado"] = False
                await asyncio.sleep(1)


@asynccontextmanager
async def ciclo(app):
    tarea = asyncio.create_task(consumir())
    yield
    tarea.cancel()


def verificar_secreto(x_internal_secret: str = Header(default="")):
    if not iguales(x_internal_secret, SECRETO):
        raise HTTPException(status_code=403, detail="Solicitud no autorizada")


app = FastAPI(
    title="Analytics Service",
    lifespan=ciclo,
    dependencies=[Depends(verificar_secreto)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
instalar_logs(app, "analytics")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "analytics",
        "stream_orders": estado_consumidor["conectado"],
        "ultimo_seq": (await checkpoint.find_one({"_id": "orders"}) or {}).get(
            "seq", 0
        ),
    }


@app.get("/reports/sales")
async def reporte_ventas(desde: date, hasta: date, ident: dict = Depends(identidad)):
    requerir_roles(ident, "dueno", "admin")
    if hasta < desde or (hasta - desde).days > 366:
        raise HTTPException(status_code=400, detail="Período inválido (máximo un año)")
    inicio = datetime.combine(desde, time.min, ZONA)
    fin = datetime.combine(hasta + timedelta(days=1), time.min, ZONA)
    filtro = {"anulado": False, "pagado_en": {"$gte": inicio, "$lt": fin}}
    totales = await ventas.aggregate(
        [
            {"$match": filtro},
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": "$total"},
                    "pedidos": {"$sum": 1},
                }
            },
        ]
    ).to_list(1)
    por_producto = await ventas.aggregate(
        [
            {"$match": filtro},
            {"$unwind": "$items"},
            {
                "$group": {
                    "_id": "$items.product_id",
                    "nombre": {"$first": "$items.nombre"},
                    "cantidad": {"$sum": "$items.cantidad"},
                    "monto": {"$sum": "$items.subtotal"},
                }
            },
            {"$sort": {"monto": -1}},
        ]
    ).to_list(200)
    cp = await checkpoint.find_one({"_id": "orders"}) or {}
    return {
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "total_ventas": totales[0]["total"] if totales else 0,
        "cantidad_pedidos": totales[0]["pedidos"] if totales else 0,
        "por_producto": [
            {
                "product_id": p["_id"],
                "nombre": p["nombre"],
                "cantidad": p["cantidad"],
                "monto": p["monto"],
            }
            for p in por_producto
        ],
        "actualizado_hasta_seq": cp.get("seq", 0),
        "retraso_aceptado_s": RETRASO_ACEPTADO_S,
    }
