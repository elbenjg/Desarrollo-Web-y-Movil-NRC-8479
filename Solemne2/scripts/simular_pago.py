"""Simula al proveedor de pagos (adaptador de prueba): envía al gateway el aviso firmado con HMAC.

Uso: py scripts\\simular_pago.py <provider_ref> <monto> [APROBADO|RECHAZADO]
Lo hace el proveedor de servidor a servidor; el navegador nunca conoce la clave de firma.
"""

import hashlib
import hmac
import json
import os
import sys
import uuid
from pathlib import Path

import httpx

archivo = Path(__file__).resolve().parents[1] / ".runtime" / "vault-token"
token = (
    archivo.read_text()
    if archivo.exists()
    else os.environ.get("VAULT_TOKEN", "dev-only-token")
)
clave = httpx.get(
    "http://127.0.0.1:8200/v1/secret/data/payments", headers={"X-Vault-Token": token}
).json()["data"]["data"]["provider_webhook_secret"]
estado = sys.argv[3] if len(sys.argv) > 3 else "APROBADO"
cuerpo = json.dumps(
    {
        "event_id": uuid.uuid4().hex,
        "provider_ref": sys.argv[1],
        "estado": estado,
        "monto": int(sys.argv[2]),
    }
).encode()
firma = hmac.new(clave.encode(), cuerpo, hashlib.sha256).hexdigest()
r = httpx.post(
    "http://127.0.0.1:8000/api/v1/payments/webhook",
    content=cuerpo,
    headers={"Content-Type": "application/json", "X-Provider-Signature": firma},
)
print(r.status_code, r.text)
