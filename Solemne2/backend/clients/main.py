# Sistema clients: registro, perfil, verificación de correo, contacto y mensajería.
import hashlib
import re
import secrets
from datetime import date, datetime, timezone
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Header, Query
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, field_validator

from comun import (
    MONGODB_URI,
    PATRON_CORREO,
    identidad,
    instalar_logs,
    llamar,
    requerir_env,
    requerir_roles,
    requerir_sesion,
    iguales,
)

SECRETO = requerir_env("CLIENTS_SECRET")
AUTH_SECRET = requerir_env("AUTH_SECRET")

db = AsyncIOMotorClient(MONGODB_URI)["fn_clients"]
clientes = db["clients"]
bandeja = db["outbox"]
mensajes = db["contact_messages"]


def verificar_secreto(x_internal_secret: str = Header(default="")):
    if not iguales(x_internal_secret, SECRETO):
        raise HTTPException(status_code=403, detail="Solicitud no autorizada")


app = FastAPI(
    title="Clients Service",
    dependencies=[Depends(verificar_secreto)],
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
instalar_logs(app, "clients")


def validar_rut(rut: str) -> str:
    limpio = re.sub(r"[.\s]", "", rut).upper()
    if not re.fullmatch(r"\d{7,8}-[0-9K]", limpio):
        raise ValueError("RUT inválido")
    cuerpo, dv = limpio.split("-")
    suma, multiplo = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * multiplo
        multiplo = 2 if multiplo == 7 else multiplo + 1
    resto = 11 - suma % 11
    esperado = {11: "0", 10: "K"}.get(resto, str(resto))
    if esperado != dv:
        raise ValueError("RUT inválido")
    return limpio


class PerfilIn(BaseModel):
    nombreCompleto: str = Field(min_length=1, max_length=100)
    direccion: str = Field(min_length=1, max_length=150)
    comuna: str = Field(min_length=1, max_length=60)
    provincia: str = Field(min_length=1, max_length=60)
    region: str = Field(min_length=1, max_length=60)
    fechaNacimiento: date
    sexo: Literal["Femenino", "Masculino", "Prefiero no decirlo"]
    telefono: str = Field(pattern=r"^\+?\d[\d\s]{7,14}$")

    @field_validator("fechaNacimiento")
    @classmethod
    def no_futura(cls, v: date):
        if v >= date.today():
            raise ValueError("Fecha de nacimiento inválida")
        return v


class RegistroIn(PerfilIn):
    run: str = Field(max_length=12)
    correo: str = Field(pattern=PATRON_CORREO, max_length=120)
    clave: str = Field(min_length=6, max_length=128)

    @field_validator("run")
    @classmethod
    def rut_valido(cls, v: str):
        return validar_rut(v)


class VerificacionIn(BaseModel):
    token: str = Field(min_length=10, max_length=100)


class ContactoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    correo: str = Field(pattern=PATRON_CORREO, max_length=120)
    asunto: str = Field(min_length=1, max_length=120)
    mensaje: str = Field(min_length=1, max_length=2000)


class NotificacionIn(BaseModel):
    user_id: str
    asunto: str = Field(max_length=200)
    cuerpo: str = Field(max_length=5000)


def cliente_dto(doc: dict) -> dict:
    campos = [
        "user_id",
        "run",
        "nombreCompleto",
        "direccion",
        "comuna",
        "provincia",
        "region",
        "fechaNacimiento",
        "sexo",
        "correo",
        "telefono",
        "email_verificado",
        "activo",
    ]
    return {c: doc.get(c) for c in campos}


async def enviar_correo(para: str, asunto: str, cuerpo: str):
    await bandeja.insert_one(
        {
            "para": para,
            "asunto": asunto,
            "cuerpo": cuerpo,
            "fecha": datetime.now(timezone.utc),
        }
    )


async def emitir_verificacion(doc: dict):
    token = secrets.token_urlsafe(24)
    await clientes.update_one(
        {"user_id": doc["user_id"]},
        {"$set": {"verify_hash": hashlib.sha256(token.encode()).hexdigest()}},
    )
    await enviar_correo(
        doc["correo"],
        "Verifica tu correo en Frío Natural",
        f"Usa este código para verificar tu cuenta: {token}",
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "clients"}


@app.post("/clients", status_code=201)
async def registrar(registro: RegistroIn, ident: dict = Depends(identidad)):
    if ident["user_id"]:
        requerir_roles(ident, "admin")
    correo = registro.correo.lower()
    if await clientes.find_one({"$or": [{"run": registro.run}, {"correo": correo}]}):
        raise HTTPException(
            status_code=409, detail="El RUN o el correo ya están registrados"
        )
    user_id = "CLI-" + secrets.token_hex(4).upper()
    doc = {
        **registro.model_dump(exclude={"clave"}),
        "user_id": user_id,
        "correo": correo,
        "fechaNacimiento": registro.fechaNacimiento.isoformat(),
        "email_verificado": False,
        "activo": True,
        "creado": datetime.now(timezone.utc),
    }
    await clientes.insert_one(doc)
    resp = await llamar(
        "auth",
        "POST",
        "/users",
        AUTH_SECRET,
        json={
            "user_id": user_id,
            "email": correo,
            "password": registro.clave,
            "roles": ["cliente"],
        },
    )
    if resp.status_code != 201:
        await clientes.delete_one({"user_id": user_id})
        raise HTTPException(
            status_code=409 if resp.status_code == 409 else 503,
            detail="No fue posible crear la cuenta",
        )
    await emitir_verificacion(doc)
    return {
        "user_id": user_id,
        "correo": correo,
        "email_verificado": False,
        "mensaje": "Te enviamos un código de verificación a tu correo",
    }


@app.post("/clients/verify-email")
async def verificar_correo(verificacion: VerificacionIn):
    doc = await clientes.find_one(
        {"verify_hash": hashlib.sha256(verificacion.token.encode()).hexdigest()}
    )
    if not doc:
        raise HTTPException(status_code=400, detail="Código de verificación inválido")
    resp = await llamar(
        "auth", "POST", f"/internal/users/{doc['user_id']}/verify", AUTH_SECRET
    )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=503, detail="No fue posible verificar la cuenta, reintenta"
        )
    await clientes.update_one(
        {"user_id": doc["user_id"]},
        {"$set": {"email_verificado": True}, "$unset": {"verify_hash": ""}},
    )
    return {"user_id": doc["user_id"], "email_verificado": True}


@app.get("/clients/me")
async def mi_perfil(ident: dict = Depends(identidad)):
    requerir_sesion(ident)
    doc = await clientes.find_one({"user_id": ident["user_id"]})
    if not doc:
        raise HTTPException(status_code=404, detail="Perfil de cliente no encontrado")
    return cliente_dto(doc)


@app.put("/clients/me")
async def actualizar_mi_perfil(perfil: PerfilIn, ident: dict = Depends(identidad)):
    requerir_sesion(ident)
    return await actualizar(ident["user_id"], perfil)


@app.get("/clients")
async def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    ident: dict = Depends(identidad),
):
    requerir_roles(ident, "admin")
    docs = (
        await clientes.find().sort("creado", -1).skip(skip).limit(limit).to_list(limit)
    )
    return [cliente_dto(d) for d in docs]


@app.get("/clients/{user_id}")
async def obtener(user_id: str, ident: dict = Depends(identidad)):
    requerir_roles(ident, "admin")
    doc = await clientes.find_one({"user_id": user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente_dto(doc)


@app.put("/clients/{user_id}")
async def actualizar_cliente(
    user_id: str, perfil: PerfilIn, ident: dict = Depends(identidad)
):
    requerir_roles(ident, "admin")
    return await actualizar(user_id, perfil)


async def actualizar(user_id: str, perfil: PerfilIn):
    cambios = {
        **perfil.model_dump(),
        "fechaNacimiento": perfil.fechaNacimiento.isoformat(),
    }
    res = await clientes.update_one({"user_id": user_id}, {"$set": cambios})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente_dto(await clientes.find_one({"user_id": user_id}))


@app.delete("/clients/{user_id}", status_code=204)
async def dar_de_baja(user_id: str, ident: dict = Depends(identidad)):
    requerir_roles(ident, "admin")
    res = await clientes.update_one({"user_id": user_id}, {"$set": {"activo": False}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    resp = await llamar(
        "auth", "POST", f"/internal/users/{user_id}/disable", AUTH_SECRET
    )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail="Cliente marcado inactivo, pero no se pudo deshabilitar su acceso",
        )


@app.post("/contact", status_code=201)
async def contacto(msg: ContactoIn):
    await mensajes.insert_one({**msg.model_dump(), "fecha": datetime.now(timezone.utc)})
    return {"mensaje": "Recibimos tu mensaje y te responderemos a la brevedad"}


@app.post("/internal/notify")
async def notificar(notif: NotificacionIn):
    doc = await clientes.find_one({"user_id": notif.user_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    await enviar_correo(doc["correo"], notif.asunto, notif.cuerpo)
    return {"enviado": True}
