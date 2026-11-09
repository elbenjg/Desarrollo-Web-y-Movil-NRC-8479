# Anexo A. Contratos: un ejemplo por servicio

Anexo del [informe de arquitectura](INFORME.md), complemento del Módulo 1. Cada ejemplo es una **ejecución real** contra el backend,
con los datos ficticios de prueba (`seed.py`). Los tokens, códigos y firmas se reemplazan por `<...>`; las listas largas se
acortan con `...`. Las rutas son las del API Gateway.

## Catálogo (inventory)

### S01 Consultar catálogo
Acceso: anónimo.
```text
GET /products?available=true
→ 200 [{"id": 1, "nombre": "Cono Vainilla Crunch", "categoria": "Conos Clásicos", "precio": 3500, "imagen": "https://...", "descripcion": "Cono Vainilla Crunch artesanal", "disponible": true}, "..."]

GET /products?available=quizas
→ 422 {"detail": [{"type": "bool_parsing", "loc": ["query", "..."], "msg": "Input should be a valid boolean, unable to interpret input", "input": "quizas"}]}
```

### S02 Ver producto
Acceso: anónimo.
```text
GET /products/1
→ 200 {"id": 1, "nombre": "Cono Vainilla Crunch", "categoria": "Conos Clásicos", "precio": 3500, "imagen": "https://...", "descripcion": "Cono Vainilla Crunch artesanal", "disponible": true}

GET /products/999
→ 404 {"detail": "Producto no encontrado"}
```

### S03 Crear producto
Acceso: admin.
```text
POST /products
{"nombre": "Cono Menta", "categoria": "Conos Clásicos", "precio": 3900, "imagen": "", "descripcion": "Cono de menta artesanal", "disponible": true, "stock": 10}
→ 201 {"id": 8, "nombre": "Cono Menta", "categoria": "Conos Clásicos", "precio": 3900, "imagen": "", "descripcion": "Cono de menta artesanal", "disponible": true, "stock": 10}

POST /products
{"nombre": "Cono Menta", "categoria": "Conos Clásicos", "precio": 3900, "imagen": "", "descripcion": "Cono de menta artesanal", "disponible": true, "stock": 10}
→ 403 {"detail": "Rol sin permiso para esta operación"}
```

### S04 Reemplazar producto
Acceso: admin.
```text
PUT /products/8
{"nombre": "Cono Menta", "categoria": "Conos Clásicos", "precio": 4100, "imagen": "", "descripcion": "Cono de menta artesanal", "disponible": true, "stock": 10}
→ 200 {"id": 8, "nombre": "Cono Menta", "categoria": "Conos Clásicos", "precio": 4100, "imagen": "", "descripcion": "Cono de menta artesanal", "disponible": true, "stock": 10}
```

### S05 Cambiar disponibilidad
Acceso: admin, dueño.
```text
PATCH /products/8/availability
{"disponible": false, "stock": 0}
→ 200 {"id": 8, "nombre": "Cono Menta", "categoria": "Conos Clásicos", "precio": 4100, "imagen": "", "descripcion": "Cono de menta artesanal", "disponible": false, "stock": 0}
```

### S06 Eliminar producto
Acceso: admin.
```text
DELETE /products/8
→ 204
```

## Sesiones y clientes (auth, clients)

### S07 Iniciar sesión
Acceso: anónimo.
```text
POST /auth/login
{"email": "ana@correo.cl", "password": "Demo1234"}
→ 200 {"access_token": "<token opaco>", "token_type": "bearer", "expires_in": 1800, "roles": ["cliente"]}

POST /auth/login
{"email": "ana@correo.cl", "password": "clave-mala"}
→ 401 {"detail": "Credenciales inválidas"}
```

### S08 Cerrar sesión
Acceso: sesión.
```text
POST /auth/logout
→ 200 {"message": "Sesión finalizada"}
```

### S09 Registrarse
Acceso: anónimo (o admin).
```text
POST /clients
{"nombreCompleto": "Camila Rojas", "run": "12.345.678-5", "direccion": "Calle 1", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana", "fechaNacimiento": "2000-01-15", "sexo": "Femenino", "correo": "camila@correo.cl", "telefono": "+56 9 8765 4321", "clave": "secreta123"}
→ 201 {"user_id": "CLI-2A1D4F97", "correo": "camila@correo.cl", "email_verificado": false, "mensaje": "Te enviamos un código de verificación a tu correo"}

POST /clients
{"nombreCompleto": "Camila Rojas", "run": "12.345.678-9", "direccion": "Calle 1", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana", "fechaNacimiento": "2000-01-15", "sexo": "Femenino", "correo": "camila@correo.cl", "telefono": "+56 9 8765 4321", "clave": "secreta123"}
→ 422 {"detail": [{"type": "value_error", "loc": ["body", "..."], "msg": "Value error, RUT inválido", "input": "12.345.678-9", "ctx": {"error": {}}}]}
```

### S10 Verificar correo
Acceso: anónimo.
```text
POST /clients/verify-email
{"token": "<código recibido por correo>"}
→ 200 {"user_id": "CLI-2A1D4F97", "email_verificado": true}

POST /clients/verify-email
{"token": "codigo-que-no-existe"}
→ 400 {"detail": "Código de verificación inválido"}
```

### S11 Ver mi perfil
Acceso: cliente.
```text
GET /clients/me
→ 200 {"user_id": "CLI-ANA", "run": "11111111-1", "nombreCompleto": "Ana Pérez Soto", "direccion": "Av. Pajaritos 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana", "fechaNacimiento": "1995-05-10", "sexo": "Prefiero no decirlo", "correo": "ana@correo.cl", "telefono": "+56 9 1234 5678", "email_verificado": true, "activo": true}
```

### S12 Editar mi perfil
Acceso: cliente.
```text
PUT /clients/me
{"nombreCompleto": "Ana Pérez Soto", "direccion": "Av. Pajaritos 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana", "fechaNacimiento": "2000-01-15", "sexo": "Femenino", "telefono": "+56 9 8765 4321"}
→ 200 {"user_id": "CLI-ANA", "run": "11111111-1", "nombreCompleto": "Ana Pérez Soto", "direccion": "Av. Pajaritos 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana", "fechaNacimiento": "2000-01-15", "sexo": "Femenino", "correo": "ana@correo.cl", "telefono": "+56 9 8765 4321", "email_verificado": true, "activo": true}
```

### S13 Listar clientes
Acceso: admin.
```text
GET /clients?skip=0&limit=2
→ 200 [{"user_id": "CLI-2A1D4F97", "run": "12345678-5", "nombreCompleto": "Camila Rojas", "direccion": "Calle 1", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana", "fechaNacimiento": "2000-01-15", "sexo": "Femenino", "correo": "camila@correo.cl", "telefono": "+56 9 8765 4321", "email_verificado": true, "activo": true}, "..."]

GET /clients
→ 403 {"detail": "Rol sin permiso para esta operación"}
```

### S14 Ver cliente
Acceso: admin.
```text
GET /clients/CLI-ANA
→ 200 {"user_id": "CLI-ANA", "run": "11111111-1", "nombreCompleto": "Ana Pérez Soto", "direccion": "Av. Pajaritos 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana", "fechaNacimiento": "2000-01-15", "sexo": "Femenino", "correo": "ana@correo.cl", "telefono": "+56 9 8765 4321", "email_verificado": true, "activo": true}
```

### S15 Editar cliente
Acceso: admin.
```text
PUT /clients/CLI-2A1D4F97
{"nombreCompleto": "Camila Rojas", "direccion": "Calle 1", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana", "fechaNacimiento": "2000-01-15", "sexo": "Femenino", "telefono": "+56 9 8765 4321"}
→ 200 {"user_id": "CLI-2A1D4F97", "run": "12345678-5", "nombreCompleto": "Camila Rojas", "direccion": "Calle 1", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana", "fechaNacimiento": "2000-01-15", "sexo": "Femenino", "correo": "camila@correo.cl", "telefono": "+56 9 8765 4321", "email_verificado": true, "activo": true}
```

### S16 Dar de baja (lógica)
Acceso: admin.
```text
DELETE /clients/CLI-2A1D4F97
→ 204
```

### S17 Formulario de contacto
Acceso: anónimo.
```text
POST /contact
{"nombre": "Camila Rojas", "correo": "camila@correo.cl", "asunto": "Horarios", "mensaje": "¿Abren los domingos?"}
→ 201 {"mensaje": "Recibimos tu mensaje y te responderemos a la brevedad"}
```

## Pedidos y boletas (orders)

### S18 Crear pedido
Acceso: cliente.
```text
POST /orders
{"items": [{"product_id": 1, "cantidad": 2}, {"product_id": 3, "cantidad": 1}], "envio": {"direccion": "Av. Pajaritos 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana"}}
→ 201 {"id": "PED-000001", "estado": "PENDIENTE_PAGO", "items": [{"product_id": 1, "nombre": "Cono Vainilla Crunch", "precio_unitario": 3500, "cantidad": 2, "subtotal": 7000}, "..."], "total": 12200, "creado": "2026-11-05T22:29:50.110292+00:00", "historial": [{"estado": "PENDIENTE_PAGO", "fecha": "2026-11-05T22:29:50.110296+00:00", "por": "CLI-ANA"}], "motivo_anulacion": null, "envio": {"direccion": "Av. Pajaritos 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana"}}

POST /orders
{"items": [{"product_id": 5, "cantidad": 50}, {"product_id": 5, "cantidad": 50}], "envio": {"direccion": "Av. Pajaritos 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana"}}
→ 409 {"detail": "Producto 5 sin stock o no disponible"}
```

### S19 Listar pedidos
Acceso: sesión (el cliente solo ve los suyos).
```text
GET /orders?limit=1
→ 200 {"total": 1, "pedidos": [{"id": "PED-000001", "estado": "PENDIENTE_PAGO", "items": [{"product_id": 1, "nombre": "Cono Vainilla Crunch", "precio_unitario": 3500, "cantidad": 2, "subtotal": 7000}, "..."], "total": 12200, "creado": "2026-11-05T22:29:50.110000+00:00", "historial": [{"estado": "PENDIENTE_PAGO", "fecha": "2026-11-05T22:29:50.110000+00:00", "por": "CLI-ANA"}], "motivo_anulacion": null, "envio": {"direccion": "Av. Pajaritos 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana"}}]}
```

### S20 Ver pedido
Acceso: sesión (propio o personal).
```text
GET /orders/PED-000001
→ 200 {"id": "PED-000001", "estado": "PENDIENTE_PAGO", "items": [{"product_id": 1, "nombre": "Cono Vainilla Crunch", "precio_unitario": 3500, "cantidad": 2, "subtotal": 7000}, "..."], "total": 12200, "creado": "2026-11-05T22:29:50.110000+00:00", "historial": [{"estado": "PENDIENTE_PAGO", "fecha": "2026-11-05T22:29:50.110000+00:00", "por": "CLI-ANA"}], "motivo_anulacion": null, "envio": {"direccion": "Av. Pajaritos 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana"}}

GET /orders/PED-000001
→ 404 {"detail": "Pedido no encontrado"}
```

### S21 Anular pedido
Acceso: cliente (propio), admin.
```text
POST /orders/PED-000003/cancel
{"motivo": "Me equivoqué de sabor"}
→ 200 {"id": "PED-000003", "estado": "ANULADO", "items": [{"product_id": 1, "nombre": "Cono Vainilla Crunch", "precio_unitario": 3500, "cantidad": 2, "subtotal": 7000}, "..."], "total": 12200, "creado": "2026-11-05T22:29:50.252000+00:00", "historial": [{"estado": "PENDIENTE_PAGO", "fecha": "2026-11-05T22:29:50.252000+00:00", "por": "CLI-ANA"}, "..."], "motivo_anulacion": "Me equivoqué de sabor", "envio": {"direccion": "Av. Pajaritos 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana"}}

POST /orders/PED-000003/cancel
{"motivo": "Lo intento de nuevo"}
→ 409 {"detail": "No se puede anular un pedido en estado ANULADO"}
```

## Pagos (payments)

### S26 Iniciar pago
Acceso: cliente (pedido propio).
```text
POST /payments
{"order_id": "PED-000001", "metodo": "Webpay"}
→ 201 {"id": "PAG-5C029B38BE", "order_id": "PED-000001", "monto": 12200, "metodo": "Webpay", "estado": "PENDIENTE", "provider_ref": "SBX-d328b99306a32890", "creado": "2026-11-05T22:29:50.331641+00:00", "checkout_url": "https://sandbox.proveedor.example/pay/SBX-d328b99306a32890"}

POST /payments
{"order_id": "PED-000001", "metodo": "Webpay"}
→ 404 {"detail": "Pedido no encontrado"}
```

### S27 Ver pago
Acceso: sesión (propio o personal).
```text
GET /payments/PAG-5C029B38BE
→ 200 {"id": "PAG-5C029B38BE", "order_id": "PED-000001", "monto": 12200, "metodo": "Webpay", "estado": "PENDIENTE", "provider_ref": "SBX-d328b99306a32890", "creado": "2026-11-05T22:29:50.331000+00:00"}
```

### S28 Aviso del proveedor
Acceso: anónimo + firma HMAC-SHA256 del cuerpo en `X-Provider-Signature`. Ejemplos: aviso válido, repetido y sin firma.
```text
POST /payments/webhook
{"event_id": "evt-001", "provider_ref": "SBX-d328b99306a32890", "estado": "APROBADO", "monto": 12200}
→ 200 {"procesado": true, "estado": "APROBADO"}

POST /payments/webhook
{"event_id": "evt-001", "provider_ref": "SBX-d328b99306a32890", "estado": "APROBADO", "monto": 12200}
→ 200 {"procesado": false, "duplicado": true}

POST /payments/webhook
{"event_id": "evt-001", "provider_ref": "SBX-d328b99306a32890", "estado": "APROBADO", "monto": 12200}
→ 401 {"detail": "Firma inválida"}
```

## Despacho, boleta y reporte

### S22 Avanzar estado
Acceso: despacho, admin.
```text
PATCH /orders/PED-000001/status
{"estado": "EN_PREPARACION"}
→ 200 {"id": "PED-000001", "estado": "EN_PREPARACION", "items": [{"product_id": 1, "nombre": "Cono Vainilla Crunch", "precio_unitario": 3500, "cantidad": 2, "subtotal": 7000}, "..."], "total": 12200, "creado": "2026-11-05T22:29:50.110000+00:00", "historial": [{"estado": "PENDIENTE_PAGO", "fecha": "2026-11-05T22:29:50.110000+00:00", "por": "CLI-ANA"}, "..."], "motivo_anulacion": null, "envio": {"direccion": "Av. Pajaritos 1234", "comuna": "Maipú", "provincia": "Santiago", "region": "Metropolitana"}, "user_id": "CLI-ANA"}

PATCH /orders/PED-000001/status
{"estado": "ENTREGADO"}
→ 409 {"detail": "Transición inválida: EN_PREPARACION -> ENTREGADO"}
```

### S23 Emitir boleta
Acceso: cajero, admin.
```text
POST /orders/PED-000001/receipt
→ 201 {"numero": 1, "order_id": "PED-000001", "user_id": "CLI-ANA", "items": [{"product_id": 1, "nombre": "Cono Vainilla Crunch", "precio_unitario": 3500, "cantidad": 2, "subtotal": 7000}, "..."], "neto": 10252, "iva": 1948, "total": 12200, "fecha": "2026-11-05T22:29:50.797147+00:00", "emitida_por": "USR-CAJERO", "enviada": true}

POST /orders/PED-000001/receipt
→ 403 {"detail": "Rol sin permiso para esta operación"}
```

### S24 Ver boleta
Acceso: sesión (propia o personal).
```text
GET /orders/PED-000001/receipt
→ 200 {"numero": 1, "order_id": "PED-000001", "user_id": "CLI-ANA", "items": [{"product_id": 1, "nombre": "Cono Vainilla Crunch", "precio_unitario": 3500, "cantidad": 2, "subtotal": 7000}, "..."], "neto": 10252, "iva": 1948, "total": 12200, "fecha": "2026-11-05T22:29:50.797000+00:00", "emitida_por": "USR-CAJERO", "enviada": true}
```

### S25 Reporte de ventas
Acceso: dueño, admin.
```text
GET /reports/sales?desde=2026-11-05&hasta=2026-11-05
→ 200 {"desde": "2026-11-05", "hasta": "2026-11-05", "total_ventas": 12200, "cantidad_pedidos": 1, "por_producto": [{"product_id": 1, "nombre": "Cono Vainilla Crunch", "cantidad": 2, "monto": 7000}, "..."], "actualizado_hasta_seq": 5, "retraso_aceptado_s": 5}

GET /reports/sales?desde=2026-11-05&hasta=2026-11-05
→ 403 {"detail": "Rol sin permiso para esta operación"}
```

## Administración de usuarios (auth)

### S29 Listar usuarios
Acceso: admin.
```text
GET /admin/users
→ 200 [{"user_id": "USR-ADMIN", "email": "admin@frionatural.cl", "roles": ["admin"], "activo": true, "email_verificado": true}, "..."]
```

### S30 Crear usuario
Acceso: admin.
```text
POST /admin/users
{"email": "cajero2@frionatural.cl", "password": "Demo1234", "roles": ["cajero"]}
→ 201 {"user_id": "USR-DB0AD225", "email": "cajero2@frionatural.cl", "roles": ["cajero"], "activo": true, "email_verificado": true}
```

### S31 Asignar perfil
Acceso: admin.
```text
PUT /admin/users/USR-DB0AD225
{"roles": ["despacho"], "activo": true}
→ 200 {"user_id": "USR-DB0AD225", "email": "cajero2@frionatural.cl", "roles": ["despacho"], "activo": true, "email_verificado": true}
```

## Agregación y tiempo real

### S32 Consulta GraphQL (G01 resumenPedido)
Acceso: sesión; autorización por recurso y campo.
```text
POST /graphql
{"query": "query($id: ID!) { resumenPedido(id: $id) { id estado total items { nombre cantidad producto { categoria disponible } } pagos { estado monto } envio { comuna } } }", "variables": {"id": "PED-000001"}}
→ 200 {"data": {"resumenPedido": {"id": "PED-000001", "estado": "EN_PREPARACION", "total": 12200, "items": [{"nombre": "Cono Vainilla Crunch", "cantidad": 2, "producto": {"categoria": "Conos Clásicos", "disponible": true}}, "..."], "pagos": [{"estado": "APROBADO", "monto": 12200}], "envio": {"comuna": "Maipú"}}}}

POST /graphql
{"query": "query($id: ID!) { resumenPedido(id: $id) { id envio { comuna } } }", "variables": {"id": "PED-000001"}}
→ 200 {"errors": [{"message": "Campo envio restringido para tu rol", "path": ["resumenPedido", "..."], "extensions": {"code": "FORBIDDEN"}}], "data": {"resumenPedido": {"id": "PED-000001", "envio": null}}}
```

### S32 Consulta GraphQL (G02 pedidos)
Acceso: sesión; cada cliente solo los suyos.
```text
POST /graphql
{"query": "{ pedidos(pagina: 1, porPagina: 1) { total pedidos { id estado total } } }"}
→ 200 {"data": {"pedidos": {"total": 2, "pedidos": [{"id": "PED-000003", "estado": "ANULADO", "total": 12200}]}}}
```

### S32 Consulta GraphQL (G03 reporteVentas)
Acceso: dueño, admin.
```text
POST /graphql
{"query": "{ reporteVentas(desde: \"2026-11-05\", hasta: \"2026-11-05\") { totalVentas cantidadPedidos porProducto { nombre categoria monto } } }"}
→ 200 {"data": {"reporteVentas": {"totalVentas": 12200, "cantidadPedidos": 1, "porProducto": [{"nombre": "Cono Vainilla Crunch", "categoria": "Conos Clásicos", "monto": 7000}, "..."]}}}
```

### S33 Panel de despacho en vivo (SSE)
Acceso: despacho, admin. Se muestra el primer evento; la conexión sigue abierta.
```text
GET /dispatch/events   (Last-Event-ID: 0)
→ 200 text/event-stream
retry: 3000
id: 1
event: estado
data: {"order_id": "PED-000001", "estado": "PENDIENTE_PAGO", "fecha": "2026-11-05T22:29:50.111000+00:00", "total": 12200, "items": [{"nombre": "Cono Vainilla Crunch", "cantidad": 2}, {"nombre": "Copa Frutos Rojos", "cantidad": 1}]}

GET /dispatch/events
→ 403 {"detail": "Rol sin permiso para esta operación"}
```
