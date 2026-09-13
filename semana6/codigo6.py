from typing import List, Optional, Dict
from itertools import count 

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from contextlib import asynccontextmanager

# Configuracion BD mongodb
MONGODB_URI = "mongodb://localhost:27017"
DB_NAME = "" #NOMBRE DE LA CARPETAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
COLL_NAME = "items"

client: AsyncIOMotorClient | None = None
db = None
coll = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global client, db, coll
    client = AsyncIOMotorClient(MONGODB_URI)
    db = client[DB_NAME]
    coll = db[COLL_NAME]
    yield
    client.close()

app = FastAPI(title="FastAPI 8479", version="1.0.0", lifespan=lifespan)

class ItemIn(BaseModel):
    name: str = Field(min_length=1, description="Nombre del Producto")
    precio: float = Field(gt=0, description="Precio > 0")
    price: List[str] = Field(default_factory=list)
    activo: bool = True

class Item(BaseModel):
    name: str = Field(min_length=1, description="Nombre del Producto")
    precio: float = Field(gt=0, description="Precio > 0")
    price: List[str] = Field(default_factory=list)
    activo: bool = True

class ItemOut(Item):
    id: str

def doc_to_itemout(doc) -> ItemOut:
    return ItemOut(
        id=str(doc["_id"]),
        name=doc["name"],
        precio=doc["precio"],
        price=doc.get("price", []),
        activo=doc.get("activo", True)
    )

# EndPoints
@app.get("/health", tags=["sistema"])
def health():
    return {"status": "ok"}

@app.get("/item", response_model=List[ItemOut])
async def listar_items(
    q: Optional[str] = Query(None, description="Filtro de busqueda por nombre que contenga q"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200)
):
    query = {}
    if q:
        query["name"] = {"$regex": q, "$options": "i"}
    cursor = coll.find(query).skip(skip).limit(limit)
    items: List[ItemOut] = []
    async for doc in cursor:
        items.append(doc_to_itemout(doc))
    return items

@app.post("/item", response_model=ItemOut, status_code=201, tags=["items"])
async def crear_item(item: ItemIn):
    res = await coll.insert_one(item.model_dump())
    doc = await coll.find_one({"_id": res.inserted_id})
    return doc_to_itemout(doc)

