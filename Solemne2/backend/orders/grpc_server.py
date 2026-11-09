# Servidor gRPC de orders (contrato proto/seguimiento.proto).
import asyncio
import logging
import os
import time
from pathlib import Path

import grpc
from pymongo.errors import PyMongoError

import seguimiento_pb2 as pb
import seguimiento_pb2_grpc as pb_grpc
from comun import iguales, requerir_env

DIRECCION = os.getenv("ORDERS_GRPC_ADDR", "127.0.0.1:50051")
CONSUMIDORES = {
    "analytics": requerir_env("GRPC_ANALYTICS_SECRET"),
    "gateway": requerir_env("GRPC_GATEWAY_SECRET"),
}
PERMISOS = {"SeguirEventos": {"analytics", "gateway"}, "UltimoSeq": {"gateway"}}
LOTE = 100
ESPERA_S = 0.3
HUECO_MAX_S = 2.0
MAX_STREAMS = 50

log = logging.getLogger("orders.grpc")


def a_mensaje(d: dict) -> pb.EventoPedido:
    return pb.EventoPedido(
        seq=d["seq"],
        order_id=d["order_id"],
        estado=d["estado"],
        fecha=d["fecha"].isoformat(),
        total=d["total"],
        items=[pb.Linea(**i) for i in d["items"]],
    )


class Seguimiento(pb_grpc.SeguimientoServicer):
    def __init__(self, eventos):
        self.eventos = eventos
        self.activos = 0

    async def autorizar(self, context, metodo: str) -> str:
        metadata = dict(context.invocation_metadata())
        secreto = metadata.get("x-internal-secret", "")
        consumidor = next(
            (n for n, s in CONSUMIDORES.items() if iguales(secreto, s)), None
        )
        log.info(
            "cid=%s %s consumidor=%s",
            metadata.get("x-correlation-id", "-"),
            metodo,
            consumidor,
        )
        if consumidor is None:
            await context.abort(
                grpc.StatusCode.UNAUTHENTICATED, "Credencial de servicio inválida"
            )
        if consumidor not in PERMISOS[metodo]:
            await context.abort(
                grpc.StatusCode.PERMISSION_DENIED,
                f"{consumidor} no puede invocar {metodo}",
            )
        return consumidor

    async def UltimoSeq(self, request, context):
        await self.autorizar(context, "UltimoSeq")
        try:
            ultimo = await self.eventos.find_one({}, sort=[("seq", -1)])
        except PyMongoError:
            await context.abort(
                grpc.StatusCode.UNAVAILABLE, "Base de datos no disponible"
            )
        return pb.UltimoSeqResponse(seq=ultimo["seq"] if ultimo else 0)

    async def SeguirEventos(self, request, context):
        await self.autorizar(context, "SeguirEventos")
        if request.desde_seq < 0:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "desde_seq debe ser >= 0"
            )
        if self.activos >= MAX_STREAMS:
            await context.abort(
                grpc.StatusCode.RESOURCE_EXHAUSTED, "Demasiados streams abiertos"
            )
        self.activos += 1
        ultimo, hueco = request.desde_seq, None
        try:
            while True:
                try:
                    docs = (
                        await self.eventos.find({"seq": {"$gt": ultimo}})
                        .sort("seq", 1)
                        .limit(LOTE)
                        .to_list(LOTE)
                    )
                except PyMongoError:
                    await context.abort(
                        grpc.StatusCode.UNAVAILABLE, "Base de datos no disponible"
                    )
                enviados = 0
                for d in docs:
                    if d["seq"] != ultimo + 1:
                        hueco = hueco or time.monotonic()
                        if time.monotonic() - hueco < HUECO_MAX_S:
                            break
                    hueco = None
                    yield a_mensaje(d)
                    ultimo = d["seq"]
                    enviados += 1
                if enviados < LOTE:
                    await asyncio.sleep(ESPERA_S)
        finally:
            self.activos -= 1


async def iniciar_servidor(eventos):
    tls = grpc.ssl_server_credentials(
        [
            (
                Path(requerir_env("GRPC_TLS_KEY")).read_bytes(),
                Path(requerir_env("GRPC_TLS_CERT")).read_bytes(),
            )
        ]
    )
    servidor = grpc.aio.server(
        options=[
            ("grpc.max_receive_message_length", 16 * 1024),
            ("grpc.max_send_message_length", 64 * 1024),
        ]
    )
    pb_grpc.add_SeguimientoServicer_to_server(Seguimiento(eventos), servidor)
    servidor.add_secure_port(DIRECCION, tls)
    await servidor.start()
    log.info("gRPC escuchando en %s (TLS)", DIRECCION)
    return servidor
