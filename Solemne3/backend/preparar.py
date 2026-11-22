# Prepara el entorno antes de que arranquen los contenedores: secretos en Vault, token del gateway,
# certificado TLS de gRPC, variables de cada servicio y datos de prueba.
import secrets
import subprocess
import sys
from pathlib import Path

import httpx

from comun import requerir_env

COMPARTIDO = Path("/compartido")
TLS = COMPARTIDO / "tls"
CRT, KEY = str(TLS / "orders.crt"), str(TLS / "orders.key")

token_raiz = (COMPARTIDO / "vault-token").read_text().strip()
vault = httpx.Client(
    base_url=requerir_env("VAULT_ADDR") + "/v1",
    headers={"X-Vault-Token": token_raiz},
    timeout=5,
)


def nuevo() -> str:
    return secrets.token_hex(32)


if vault.get("secret/data/gateway").status_code == 200:
    print("Vault ya tiene los secretos de esta ejecución; se reutilizan")
else:
    gw = {
        s: nuevo()
        for s in (
            "auth",
            "inventory",
            "orders",
            "clients",
            "payments",
            "graphql",
            "analytics",
            "grpc_gateway",
        )
    }
    webhook, grpc_analytics = nuevo(), nuevo()
    for ruta, datos in (
        ("gateway", gw),
        ("payments", {"provider_webhook_secret": webhook}),
        ("analytics", {"grpc_analytics": grpc_analytics}),
    ):
        vault.post(f"secret/data/{ruta}", json={"data": datos}).raise_for_status()
    vault.put(
        "sys/policies/acl/gateway-read",
        json={"policy": Path("gateway-read.hcl").read_text()},
    ).raise_for_status()
    token_gateway = vault.post(
        "auth/token/create", json={"policies": ["gateway-read"], "ttl": "24h"}
    ).json()["auth"]["client_token"]

    TLS.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "2",
            "-subj",
            "/CN=orders-grpc",
            "-addext",
            "subjectAltName=IP:127.0.0.1,DNS:localhost,DNS:orders",
            "-keyout",
            KEY,
            "-out",
            CRT,
        ],
        check=True,
        capture_output=True,
    )

    variables = {
        "auth": {"AUTH_SECRET": gw["auth"]},
        "inventory": {"INVENTORY_SECRET": gw["inventory"]},
        "clients": {"CLIENTS_SECRET": gw["clients"], "AUTH_SECRET": gw["auth"]},
        "orders": {
            "ORDERS_SECRET": gw["orders"],
            "INVENTORY_SECRET": gw["inventory"],
            "CLIENTS_SECRET": gw["clients"],
            "GRPC_GATEWAY_SECRET": gw["grpc_gateway"],
            "GRPC_ANALYTICS_SECRET": grpc_analytics,
            "GRPC_TLS_CERT": CRT,
            "GRPC_TLS_KEY": KEY,
        },
        "payments": {
            "PAYMENTS_SECRET": gw["payments"],
            "ORDERS_SECRET": gw["orders"],
            "PROVIDER_WEBHOOK_SECRET": webhook,
        },
        "analytics": {
            "ANALYTICS_SECRET": gw["analytics"],
            "GRPC_ANALYTICS_SECRET": grpc_analytics,
            "GRPC_TLS_CA": CRT,
        },
        "graphql": {
            "GRAPHQL_SECRET": gw["graphql"],
            "ORDERS_SECRET": gw["orders"],
            "INVENTORY_SECRET": gw["inventory"],
            "PAYMENTS_SECRET": gw["payments"],
            "ANALYTICS_SECRET": gw["analytics"],
        },
        "gateway": {"VAULT_TOKEN": token_gateway, "GRPC_TLS_CA": CRT},
    }
    (COMPARTIDO / "env").mkdir(exist_ok=True)
    for servicio, valores in variables.items():
        (COMPARTIDO / "env" / f"{servicio}.env").write_text(
            "".join(f"export {k}={v}\n" for k, v in valores.items())
        )
    print("Secretos, token del gateway, certificado TLS y variables listos")

subprocess.run([sys.executable, "seed.py"], check=True)
