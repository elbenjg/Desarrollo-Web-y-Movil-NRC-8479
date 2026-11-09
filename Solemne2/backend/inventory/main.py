# Sistema inventory: catálogo, disponibilidad y stock.
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Header, Query
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from comun import (
    MONGODB_URI,
    identidad,
    instalar_logs,
    requerir_env,
    requerir_roles,
    iguales,
)

SECRETO = requerir_env("INVENTORY_SECRET")

db = AsyncIOMotorClient(MONGODB_URI)["fn_inventory"]
productos = db["products"]
reservas = db["reservations"]


def verificar_secreto(x_internal_secret: str = Header(default="")):
    if not iguales(x_internal_secret, SECRETO):
        raise HTTPException(status_code=403, detail="Solicitud no autorizada")


app = FastAPI(
    title="Inventory Service",
    dependencies=[Depends(verificar_secreto)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
instalar_logs(app, "inventory")

CAMPOS_PUBLICOS = {
    "_id": 0,
    "id": 1,
    "nombre": 1,
    "categoria": 1,
    "precio": 1,
    "imagen": 1,
    "descripcion": 1,
    "disponible": 1,
}


class ProductoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    categoria: str = Field(min_length=1, max_length=40)
    precio: int = Field(gt=0, le=1_000_000, description="Precio en CLP")
    imagen: str = Field(default="", max_length=500)
    descripcion: str = Field(default="", max_length=500)
    disponible: bool = True
    stock: int = Field(ge=0, le=100_000)


class DisponibilidadIn(BaseModel):
    disponible: bool
    stock: Optional[int] = Field(default=None, ge=0, le=100_000)


class ItemReserva(BaseModel):
    product_id: int
    cantidad: int = Field(gt=0, le=1000)


class ReservaIn(BaseModel):
    order_id: str = Field(min_length=1, max_length=40)
    items: List[ItemReserva] = Field(min_length=1, max_length=20)


def proyeccion(ident: dict) -> dict:
    if {"admin", "dueno"} & set(ident["roles"]):
        return {**CAMPOS_PUBLICOS, "stock": 1}
    return CAMPOS_PUBLICOS


@app.get("/health")
def health():
    return {"status": "ok", "service": "inventory"}


@app.get("/products")
async def listar(
    available: Optional[bool] = None,
    categoria: Optional[str] = Query(None, max_length=40),
    ids: Optional[str] = Query(
        None,
        max_length=200,
        description="Lista separada por comas, usada por GraphQL para agrupar",
    ),
    ident: dict = Depends(identidad),
):
    filtro = {}
    if available is not None:
        filtro["disponible"] = available
    if categoria:
        filtro["categoria"] = categoria
    if ids:
        try:
            filtro["id"] = {"$in": [int(i) for i in ids.split(",")]}
        except ValueError:
            raise HTTPException(status_code=400, detail="ids inválidos")
    return await productos.find(filtro, proyeccion(ident)).sort("id", 1).to_list(200)


@app.get("/products/{product_id}")
async def obtener(product_id: int, ident: dict = Depends(identidad)):
    doc = await productos.find_one({"id": product_id}, proyeccion(ident))
    if not doc:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return doc


@app.post("/products", status_code=201)
async def crear(producto: ProductoIn, ident: dict = Depends(identidad)):
    requerir_roles(ident, "admin")
    ultimo = await productos.find_one({}, sort=[("id", -1)])
    doc = {"id": (ultimo["id"] + 1) if ultimo else 1, **producto.model_dump()}
    await productos.insert_one(doc)
    return await productos.find_one({"id": doc["id"]}, proyeccion(ident))


@app.put("/products/{product_id}")
async def reemplazar(
    product_id: int, producto: ProductoIn, ident: dict = Depends(identidad)
):
    requerir_roles(ident, "admin")
    res = await productos.update_one(
        {"id": product_id}, {"$set": producto.model_dump()}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return await productos.find_one({"id": product_id}, proyeccion(ident))


@app.patch("/products/{product_id}/availability")
async def cambiar_disponibilidad(
    product_id: int, cambio: DisponibilidadIn, ident: dict = Depends(identidad)
):
    requerir_roles(ident, "admin", "dueno")
    res = await productos.update_one(
        {"id": product_id}, {"$set": cambio.model_dump(exclude_none=True)}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return await productos.find_one({"id": product_id}, proyeccion(ident))


@app.delete("/products/{product_id}", status_code=204)
async def eliminar(product_id: int, ident: dict = Depends(identidad)):
    requerir_roles(ident, "admin")
    res = await productos.delete_one({"id": product_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Producto no encontrado")


@app.post("/internal/reserve")
async def reservar(reserva: ReservaIn):
    previa = await reservas.find_one({"order_id": reserva.order_id}, {"_id": 0})
    if previa:
        return previa
    reservados, lineas = [], []
    for item in reserva.items:
        doc = await productos.find_one_and_update(
            {
                "id": item.product_id,
                "disponible": True,
                "stock": {"$gte": item.cantidad},
            },
            {"$inc": {"stock": -item.cantidad}},
        )
        if not doc:
            for previo in reservados:
                await productos.update_one(
                    {"id": previo.product_id}, {"$inc": {"stock": previo.cantidad}}
                )
            raise HTTPException(
                status_code=409,
                detail=f"Producto {item.product_id} sin stock o no disponible",
            )
        reservados.append(item)
        lineas.append(
            {
                "product_id": doc["id"],
                "nombre": doc["nombre"],
                "precio_unitario": doc["precio"],
                "cantidad": item.cantidad,
            }
        )
    doc_reserva = {"order_id": reserva.order_id, "estado": "ACTIVA", "items": lineas}
    await reservas.insert_one(dict(doc_reserva))
    return doc_reserva


@app.post("/internal/release/{order_id}")
async def liberar(order_id: str):
    reserva = await reservas.find_one_and_update(
        {"order_id": order_id, "estado": "ACTIVA"}, {"$set": {"estado": "LIBERADA"}}
    )
    if reserva:
        for linea in reserva["items"]:
            await productos.update_one(
                {"id": linea["product_id"]}, {"$inc": {"stock": linea["cantidad"]}}
            )
    return {"order_id": order_id, "liberada": bool(reserva)}
