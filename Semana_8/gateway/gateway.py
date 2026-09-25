import os #SELINUX
import secrets
import httpx

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    Response
)

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials 
)

app = FastAPI(title="Local API Gateway")

security = HTTPBearer(
    auto_error=False
)

VAULT_ADDR = os.getenv(
    "VAULT_ADDR", "http://localhost:8200"
)  # Replace with your Vault address

VAULT_TOKEN = os.getenv(
    "VAULT_TOKEN" # dev-only-token 
)  # Replace with your Vault token

if not VAULT_TOKEN:
    raise ValueError(
        "VAULT_TOKEN no esta configurado."
    )

async def get_gateway_secret():
    url = (
        f"{VAULT_ADDR}" # http://localhost:8200
        "/v1/secret/data/gateway"
    )
    headers = {
        "X-Vault-Token": VAULT_TOKEN #dev-only-token
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(
            url=url,
            headers=headers
        )
    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail="Error bo fue posible acceder a Vault: {response}"
        )
    vault_response = response.json()
    return vault_response["data"]["data"]

async def authenticate_client(
        credentials:
            HTTPAuthorizationCredentials = Depends(security)
):
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Bearer token requerido"
        )
    vault_secrets = (
        await get_gateway_secret()
    )
    expected_token = vault_secrets["client_token"]
    received_token = credentials.credentials
    valid = secrets.compare_digest(received_token, expected_token)
    if not valid:
        raise HTTPException(
            status_code=401,
            detail="Token inválido"
        )
    return {"client_id": "student-client", "backend_secret": vault_secrets["backend_share_secret"]}


BACKEND_URL = "http://localhost:8000"  # Replace with your backend service URL
BACKEND_URL2 = "http://localhost:8001"  # Replace with your second backend service URL

@app.api_route(
    "api/{path:path}", #Products health orders
    methods=["GET", "POST", "PUT","PATCH", "DELETE"]
)
async def proxy(
    path: str,
    request: Request,
    auth=Depends(authenticate_client)
):
    target_url = (
        f"{BACKEND_URL}/{path}" #http://localhost:9000/products
    )
    body = await request.body()
    gateway_headers ={
        "X-Gateway-Secret":
        auth["backend_secret"], #gateway-api-secret-456
        "X-Authenticated-Client": 
        auth["client_id"] #student-client
    }
    content_type = request.headers.get("content-type") #pdf
    if content_type:
        gateway_headers["content-type"] = content_type
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            upstream = await client.request(
                method=request.method, #GET, POST, PUT, PATCH, DELETE
                url=target_url, #http://localhost:9000/products
                params=request.query_params, # http://localhost:9000/products?var=1&var2=3
                content=body, #request body
            headers=gateway_headers
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Error al comunicarse con el servicio backend"
        )
    response_headers = {}
    if "content-type" in upstream.headers:
        response_headers["content-type"] = upstream.headers["content-type"]
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers
    )