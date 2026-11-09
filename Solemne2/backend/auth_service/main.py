# Auth Service: credenciales, sesiones y roles.
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Header
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field

from comun import (
    MONGODB_URI,
    PATRON_CORREO,
    hash_clave,
    identidad,
    instalar_logs,
    requerir_env,
    requerir_roles,
    iguales,
    verificar_clave,
)

SECRETO = requerir_env("AUTH_SECRET")
TOKEN_LIFETIME_MINUTES = 30
ROLES_VALIDOS = {"cliente", "admin", "dueno", "cajero", "despacho"}
HASH_FICTICIO = hash_clave(secrets.token_hex(16))

db = AsyncIOMotorClient(MONGODB_URI)["fn_auth"]
usuarios = db["users"]
sesiones = db["sessions"]


def verificar_secreto(x_internal_secret: str = Header(default="")):
    if not iguales(x_internal_secret, SECRETO):
        raise HTTPException(status_code=403, detail="Solicitud no autorizada")


app = FastAPI(
    title="Authentication Service",
    dependencies=[Depends(verificar_secreto)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
instalar_logs(app, "auth")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class LoginRequest(BaseModel):
    email: str = Field(pattern=PATRON_CORREO, max_length=120)
    password: str = Field(min_length=1, max_length=128)


class TokenRequest(BaseModel):
    token: str = Field(min_length=1, max_length=200)


class UsuarioIn(BaseModel):
    user_id: Optional[str] = Field(default=None, max_length=40)
    email: str = Field(pattern=PATRON_CORREO, max_length=120)
    password: str = Field(min_length=6, max_length=128)
    roles: List[str] = Field(min_length=1)


class UsuarioCambio(BaseModel):
    roles: List[str] = Field(min_length=1)
    activo: bool


def validar_roles(roles: List[str]):
    if not set(roles) <= ROLES_VALIDOS:
        raise HTTPException(status_code=400, detail="Rol inválido")


def usuario_dto(doc: dict) -> dict:
    return {
        "user_id": doc["user_id"],
        "email": doc["email"],
        "roles": doc["roles"],
        "activo": doc["activo"],
        "email_verificado": doc["email_verificado"],
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "auth"}


@app.post("/login")
async def login(request: LoginRequest):
    user = await usuarios.find_one({"email": request.email.lower()})
    clave_valida = verificar_clave(
        request.password, user["password_hash"] if user else HASH_FICTICIO
    )
    if not user or not clave_valida:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    if not user["activo"]:
        raise HTTPException(status_code=403, detail="Cuenta deshabilitada")
    if not user["email_verificado"]:
        raise HTTPException(
            status_code=403, detail="Debes verificar tu correo antes de iniciar sesión"
        )
    access_token = secrets.token_urlsafe(32)
    await sesiones.insert_one(
        {
            "token_hash": hash_token(access_token),
            "user_id": user["user_id"],
            "roles": user["roles"],
            "expires_at": datetime.now(timezone.utc)
            + timedelta(minutes=TOKEN_LIFETIME_MINUTES),
        }
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": TOKEN_LIFETIME_MINUTES * 60,
        "roles": user["roles"],
    }


@app.post("/introspect")
async def introspect(request: TokenRequest):
    session = await sesiones.find_one({"token_hash": hash_token(request.token)})
    if session is None:
        return {"active": False}
    if datetime.now(timezone.utc) > session["expires_at"].replace(tzinfo=timezone.utc):
        await sesiones.delete_one({"_id": session["_id"]})
        return {"active": False}
    return {"active": True, "user_id": session["user_id"], "roles": session["roles"]}


@app.post("/logout")
async def logout(request: TokenRequest):
    await sesiones.delete_one({"token_hash": hash_token(request.token)})
    return {"message": "Sesión finalizada"}


@app.get("/users")
async def listar_usuarios(ident: dict = Depends(identidad)):
    requerir_roles(ident, "admin")
    return [usuario_dto(u) for u in await usuarios.find().sort("email", 1).to_list(500)]


@app.post("/users", status_code=201)
async def crear_usuario(nuevo: UsuarioIn, ident: dict = Depends(identidad)):
    if ident["user_id"]:
        requerir_roles(ident, "admin")
    elif nuevo.roles != ["cliente"]:
        raise HTTPException(
            status_code=403, detail="Solo el administrador crea cuentas de personal"
        )
    validar_roles(nuevo.roles)
    email = nuevo.email.lower()
    if await usuarios.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="El correo ya está registrado")
    doc = {
        "user_id": nuevo.user_id or "USR-" + secrets.token_hex(4).upper(),
        "email": email,
        "password_hash": hash_clave(nuevo.password),
        "roles": nuevo.roles,
        "activo": True,
        "email_verificado": bool(ident["user_id"]),
    }
    await usuarios.insert_one(doc)
    return usuario_dto(doc)


@app.put("/users/{user_id}")
async def cambiar_usuario(
    user_id: str, cambio: UsuarioCambio, ident: dict = Depends(identidad)
):
    requerir_roles(ident, "admin")
    validar_roles(cambio.roles)
    if user_id == ident["user_id"] and (
        not cambio.activo or "admin" not in cambio.roles
    ):
        raise HTTPException(
            status_code=400, detail="No puedes quitarte el rol admin ni deshabilitarte"
        )
    res = await usuarios.update_one({"user_id": user_id}, {"$set": cambio.model_dump()})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    await sesiones.delete_many({"user_id": user_id})
    return usuario_dto(await usuarios.find_one({"user_id": user_id}))


@app.post("/internal/users/{user_id}/verify")
async def marcar_verificado(user_id: str):
    res = await usuarios.update_one(
        {"user_id": user_id}, {"$set": {"email_verificado": True}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return {"user_id": user_id, "email_verificado": True}


@app.post("/internal/users/{user_id}/disable")
async def deshabilitar(user_id: str):
    await usuarios.update_one({"user_id": user_id}, {"$set": {"activo": False}})
    await sesiones.delete_many({"user_id": user_id})
    return {"user_id": user_id, "activo": False}
