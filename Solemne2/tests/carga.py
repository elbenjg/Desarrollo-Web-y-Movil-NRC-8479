# Prueba de carga reproducible (módulo 9). Mide latencia p95, throughput, errores y CPU/memoria del backend.
# Uso: $env:GATEWAY_RATE_LIMIT=100000; scripts\iniciar.ps1 -Reset; py tests\carga.py [concurrencia] [solicitudes]
# (el límite por IP se sube solo para la medición: todas las solicitudes salen de la misma máquina).
import asyncio
import json
import platform
import statistics
import sys
import time
from pathlib import Path

import grpc
import httpx
import psutil
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import seguimiento_pb2 as pb
import seguimiento_pb2_grpc as pb_grpc

GW = "http://127.0.0.1:8000/api/v1"
RUNTIME = Path(__file__).resolve().parents[1] / ".runtime"
CONCURRENCIA = int(sys.argv[1]) if len(sys.argv) > 1 else 20
SOLICITUDES = int(sys.argv[2]) if len(sys.argv) > 2 else 400
OBJETIVOS_P95_MS = {
    "catalogo": 500,
    "graphql_resumen": 800,
    "graphql_reporte": 800,
    "reporte_analytics": 500,
}
PEDIDOS_STREAM = 100
OBJETIVO_EVENTO_P95_MS = 1000
OBJETIVO_ANALYTICS_S = 5


def procesos():
    lista = []
    for pid in (RUNTIME / "pids.txt").read_text().split():
        try:
            p = psutil.Process(int(pid))
            lista += [p] + p.children(recursive=True)
        except psutil.NoSuchProcess:
            pass
    return lista


async def escenario(nombre, client, hacer):
    latencias, errores, sem = [], 0, asyncio.Semaphore(CONCURRENCIA)

    async def una():
        nonlocal errores
        async with sem:
            t = time.perf_counter()
            r = await hacer(client)
            latencias.append((time.perf_counter() - t) * 1000)
            if r.status_code != 200 or "errors" in r.text[:20]:
                errores += 1

    procs = procesos()
    for p in procs:
        p.cpu_percent(None)
    inicio = time.perf_counter()
    await asyncio.gather(*(una() for _ in range(SOLICITUDES)))
    duracion = time.perf_counter() - inicio
    cpu = sum(p.cpu_percent(None) for p in procs)
    memoria = sum(p.memory_info().rss for p in procs) / 2**20
    p95 = statistics.quantiles(latencias, n=100)[94]
    return {
        "escenario": nombre,
        "solicitudes": SOLICITUDES,
        "concurrencia": CONCURRENCIA,
        "duracion_s": round(duracion, 2),
        "throughput_rps": round(SOLICITUDES / duracion, 1),
        "p50_ms": round(statistics.median(latencias), 1),
        "p95_ms": round(p95, 1),
        "errores": errores,
        "cpu_backend_pct": round(cpu, 1),
        "memoria_backend_mb": round(memoria, 1),
        "objetivo_p95_ms": OBJETIVOS_P95_MS[nombre],
        "cumple": p95 <= OBJETIVOS_P95_MS[nombre] and errores == 0,
    }


def vault(ruta: str) -> dict:
    token = (RUNTIME / "vault-token").read_text()
    return httpx.get(
        f"http://127.0.0.1:8200/v1/{ruta}", headers={"X-Vault-Token": token}
    ).json()["data"]["data"]


async def escenario_stream(client, cliente_h):
    md = [("x-internal-secret", vault("secret/data/gateway")["grpc_gateway"])]
    ca = (RUNTIME / "tls" / "orders.crt").read_bytes()
    llegadas, inicios, errores, sem = {}, {}, 0, asyncio.Semaphore(CONCURRENCIA)
    async with grpc.aio.secure_channel(
        "127.0.0.1:50051", grpc.ssl_channel_credentials(ca)
    ) as canal:
        stub = pb_grpc.SeguimientoStub(canal)
        desde = (
            await stub.UltimoSeq(pb.UltimoSeqRequest(), metadata=md, timeout=3)
        ).seq
        stream = stub.SeguirEventos(
            pb.SeguirRequest(desde_seq=desde), metadata=md, timeout=120
        )

        async def escuchar():
            async for ev in stream:
                llegadas.setdefault(ev.order_id, time.perf_counter())

        async def un_pedido(i):
            nonlocal errores
            async with sem:
                t = time.perf_counter()
                r = await client.post(
                    f"{GW}/orders",
                    headers=cliente_h,
                    json={
                        "items": [{"product_id": i % 7 + 1, "cantidad": 1}],
                        "envio": {
                            "direccion": "Calle 1",
                            "comuna": "Maipú",
                            "provincia": "Santiago",
                            "region": "RM",
                        },
                    },
                )
                if r.status_code == 201:
                    inicios[r.json()["id"]] = t
                else:
                    errores += 1

        oyente = asyncio.create_task(escuchar())
        procs = procesos()
        for p in procs:
            p.cpu_percent(None)
        inicio = time.perf_counter()
        await asyncio.gather(*(un_pedido(i) for i in range(PEDIDOS_STREAM)))
        while set(inicios) - set(llegadas) and time.perf_counter() - inicio < 30:
            await asyncio.sleep(0.05)
        duracion = time.perf_counter() - inicio
        cpu = sum(p.cpu_percent(None) for p in procs)
        stream.cancel()
        oyente.cancel()
    mongo = MongoClient("mongodb://localhost:27017")
    ultimo = mongo.fn_orders.events.find_one(sort=[("seq", -1)])["seq"]
    while (mongo.fn_analytics.checkpoint.find_one({"_id": "orders"}) or {}).get(
        "seq", 0
    ) < ultimo:
        await asyncio.sleep(0.05)
    al_dia_s = time.perf_counter() - inicio
    lags = [(llegadas[o] - inicios[o]) * 1000 for o in inicios if o in llegadas]
    perdidos = len(inicios) - len(lags)
    p95 = statistics.quantiles(lags, n=100)[94]
    return {
        "escenario": "grpc_eventos_pedidos",
        "pedidos": PEDIDOS_STREAM,
        "concurrencia": CONCURRENCIA,
        "duracion_s": round(duracion, 2),
        "eventos_por_s": round(len(lags) / duracion, 1),
        "latencia_evento_p50_ms": round(statistics.median(lags), 1),
        "latencia_evento_p95_ms": round(p95, 1),
        "errores": errores,
        "eventos_perdidos": perdidos,
        "analytics_al_dia_s": round(al_dia_s, 2),
        "cpu_backend_pct": round(cpu, 1),
        "objetivo_evento_p95_ms": OBJETIVO_EVENTO_P95_MS,
        "objetivo_analytics_s": OBJETIVO_ANALYTICS_S,
        "cumple": p95 <= OBJETIVO_EVENTO_P95_MS
        and al_dia_s <= OBJETIVO_ANALYTICS_S
        and not errores + perdidos,
    }


async def main():
    async with httpx.AsyncClient(
        timeout=30, limits=httpx.Limits(max_connections=CONCURRENCIA)
    ) as client:

        async def login(email):
            r = await client.post(
                f"{GW}/auth/login", json={"email": email, "password": "Demo1234"}
            )
            return {"Authorization": f"Bearer {r.json()['access_token']}"}

        ana, dueno = await login("ana@correo.cl"), await login("dueno@frionatural.cl")
        pedido = (
            await client.post(
                f"{GW}/orders",
                headers=ana,
                json={
                    "items": [
                        {"product_id": 1, "cantidad": 1},
                        {"product_id": 3, "cantidad": 1},
                    ],
                    "envio": {
                        "direccion": "Calle 1",
                        "comuna": "Maipú",
                        "provincia": "Santiago",
                        "region": "RM",
                    },
                },
            )
        ).json()
        resumen = {
            "query": "query($id: ID!) { resumenPedido(id: $id) { estado total items { nombre producto { categoria } } pagos { estado } } }",
            "variables": {"id": pedido["id"]},
        }
        hoy = time.strftime("%Y-%m-%d")
        reporte = {
            "query": f'{{ reporteVentas(desde: "2026-01-01", hasta: "{hoy}") {{ totalVentas porProducto {{ nombre categoria }} }} }}'
        }

        resultados = [
            await escenario(
                "catalogo",
                client,
                lambda c: c.get(f"{GW}/products", params={"available": "true"}),
            ),
            await escenario(
                "graphql_resumen",
                client,
                lambda c: c.post(f"{GW}/graphql", headers=ana, json=resumen),
            ),
            await escenario(
                "graphql_reporte",
                client,
                lambda c: c.post(f"{GW}/graphql", headers=dueno, json=reporte),
            ),
            await escenario(
                "reporte_analytics",
                client,
                lambda c: c.get(
                    f"{GW}/reports/sales",
                    headers=dueno,
                    params={"desde": "2026-01-01", "hasta": hoy},
                ),
            ),
            await escenario_stream(client, ana),
        ]
    entorno = {
        "tipo": "medición local",
        "so": platform.platform(),
        "python": platform.python_version(),
        "cpus": psutil.cpu_count(),
        "ram_gb": round(psutil.virtual_memory().total / 2**30, 1),
        "fecha": time.strftime("%Y-%m-%d %H:%M"),
    }
    salida = {"entorno": entorno, "resultados": resultados}
    print(json.dumps(salida, indent=2, ensure_ascii=False))
    (RUNTIME / "carga.json").write_text(
        json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8"
    )


asyncio.run(main())
