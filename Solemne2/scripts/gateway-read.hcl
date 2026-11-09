# Política de Vault del API Gateway: solo puede leer sus propios secretos (secret/gateway).
path "secret/data/gateway" {
  capabilities = ["read"]
}
