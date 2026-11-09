workspace "ECOM" "Heladeria" {

    !identifiers hierarchical

    model {
        visitante = person "Visitante" "Persona que consulta informacion publica sin iniciar sesion."
        cliente = person "Cliente" "Persona autenticada que consulta productos y gestiona sus pedidos."
        operador = person "Operador" "Personal autorizado para gestionar catalogo y operaciones."

        sistema = softwareSystem "Heladeria" "Sistema que integra consulta de helados, gestion de clientes, pedidos y pagos." {
            tags "SistemaEvaluado"

            frontend = container "Frontend responsivo" "Interfaz web para visitantes, clientes y operadores." "Aplicacion web" {
                tags "Frontend"
            }

            apiGateway = container "API Gateway" "Punto de entrada al backend; enruta peticiones y aplica controles configurados." "Servicio HTTP" {
                tags "Gateway"
            
                // C3 - Componentes internos del API Gateway.
                httpEntry = component "Adaptador HTTP" "Recibe solicitudes y genera respuestas HTTP." "Modulo de entrada" {
                    tags "EntradaC3"
                }
                identityFilter = component "Filtro de acceso" "Distingue rutas publicas y aplica controles de identidad configurados." "Modulo de seguridad" {
                    tags "ControlC3"
                }
                routeDispatcher = component "Despachador de rutas" "Dirige cada solicitud al backend definido por el contrato." "Modulo de enrutamiento" {
                    tags "AplicacionC3"
                }
                errorMapper = component "Traductor de errores" "Convierte fallos controlados en respuestas consistentes sin revelar detalles sensibles." "Modulo de errores" {
                    tags "ErrorC3"
                }
}

            authService = container "Auth Service" "Autentica usuarios y suministra o valida identidad segun el contrato implementado." "Servicio de identidad" {
                tags "Seguridad"
            
                // C3 - Componentes internos del Auth Service.
                identityApi = component "API de identidad" "Atiende operaciones de autenticacion y validacion de sesion." "API interna" {
                    tags "EntradaC3"
                }
                sessionManager = component "Gestor de sesiones" "Controla vigencia y estado de sesiones o tokens implementados." "Servicio de identidad" {
                    tags "AplicacionC3"
                }
                credentialsVerifier = component "Verificador de credenciales" "Comprueba credenciales sin exponer valores sensibles." "Servicio de validacion" {
                    tags "ControlC3"
                }
                identityRepo = component "Repositorio de identidades" "Accede a los registros de identidad autorizados." "Acceso a datos" {
                    tags "PersistenciaC3"
                }
                secretsClient = component "Cliente de secretos" "Obtiene material secreto autorizado para operaciones de identidad." "Adaptador de integracion" {
                    tags "IntegracionC3"
                }
}

            secretManager = container "Administrador de secretos" "Gestiona secretos y los entrega exclusivamente a consumidores autorizados." "Servicio de secretos" {
                tags "Seguridad"
            }

            inventory = container "inventory" "Gestiona disponibilidad y catalogo de helados." "Servicio privado" {
                tags "Privado"
            }

            orders = container "orders" "Gestiona el ciclo de vida de los pedidos y cambios de estado." "Servicio privado" {
                tags "Privado"
            
                // C3 - Componentes internos de orders.
                ordersApi = component "API de pedidos" "Recibe solicitudes del gateway y consultas privadas de pedidos." "API interna" {
                    tags "EntradaC3"
                }
                accessPolicy = component "Politica de acceso a pedidos" "Restringe operaciones por rol y pertenencia del recurso." "Reglas de autorizacion" {
                    tags "ControlC3"
                }
                idempotency = component "Control de idempotencia" "Detecta reintentos duplicados de operaciones criticas." "Regla de negocio" {
                    tags "ControlC3"
                }
                orderWorkflow = component "Servicio de pedidos" "Coordina reglas, cambios de estado y dependencias del pedido." "Servicio de aplicacion" {
                    tags "AplicacionC3"
                }
                inventoryAdapter = component "Adaptador de inventario" "Consulta disponibilidad o solicita reserva de stock." "Adaptador privado" {
                    tags "IntegracionC3"
                }
                paymentAdapter = component "Adaptador de pagos" "Solicita o consulta operaciones de pago." "Adaptador privado" {
                    tags "IntegracionC3"
                }
                ordersRepo = component "Repositorio de pedidos" "Persiste pedidos y claves de operacion cuando corresponda." "Acceso a datos" {
                    tags "PersistenciaC3"
                }
}

            clients = container "clients" "Gestiona perfiles y datos de clientes." "Servicio privado" {
                tags "Privado"
            }

            payments = container "payments" "Gestiona estados de pago y la coordinacion de cobros." "Servicio privado" {
                tags "Privado"
            }

            dbInventory = container "Datos de inventario" "Persistencia del subsistema inventory." "Almacen de datos" {
                tags "BaseDatos"
            }

            dbOrders = container "Datos de pedidos" "Persistencia del subsistema orders." "Almacen de datos" {
                tags "BaseDatos"
            }

            dbClients = container "Datos de clientes" "Persistencia del subsistema clients." "Almacen de datos" {
                tags "BaseDatos"
            }

            dbPayments = container "Datos de pagos" "Persistencia del subsistema payments." "Almacen de datos" {
                tags "BaseDatos"
            }

            dbIdentity = container "Datos de identidad" "Persistencia de identidades y sesiones, si forma parte del caso." "Almacen de datos" {
                tags "BaseDatos"
            }

            graphqlGateway = container "GraphQL Gateway" "Expone una API de consulta y agrega informacion de subsistemas autorizados." "Servicio GraphQL" {
                tags "Gateway"
            
                // C3 - Componentes internos del GraphQL Gateway.
                graphqlEndpoint = component "Endpoint GraphQL" "Recibe operaciones GraphQL por la ruta publicada." "Adaptador GraphQL" {
                    tags "EntradaC3"
                }
                queryValidator = component "Validador de consultas" "Valida esquema y limites de complejidad configurados." "Validacion GraphQL" {
                    tags "ControlC3"
                }
                fieldAccess = component "Politica de acceso a campos" "Comprueba permisos para campos y recursos solicitados." "Modulo de autorizacion" {
                    tags "ControlC3"
                }
                resolvers = component "Resolvers de negocio" "Resuelve campos y coordina obtencion de datos autorizados." "Resolvers GraphQL" {
                    tags "AplicacionC3"
                }
                serviceConnectors = component "Conectores de subsistemas" "Consulta inventory, orders y clients por sus contratos internos." "Adaptadores de integracion" {
                    tags "IntegracionC3"
                }
                responseComposer = component "Compositor de respuestas" "Conserva errores y evita presentar fallos parciales como datos completos." "Modulo de resultados" {
                    tags "ErrorC3"
                }
}
        }

        // Relaciones de contexto (C1): se mantienen del paso anterior.
        visitante -> sistema "Consulta helados publicados"
        cliente -> sistema "Consulta productos y gestiona sus pedidos"
        operador -> sistema "Administra catalogo y operaciones autorizadas"


        // Relaciones entre los actores y el contenedor web; y entre contenedores.
        visitante -> sistema.frontend "Consulta el catalogo" "Navegador web"
        cliente -> sistema.frontend "Consulta y gestiona sus pedidos" "Navegador web"
        operador -> sistema.frontend "Gestiona operaciones autorizadas" "Navegador web"
        sistema.frontend -> sistema.apiGateway "Envia solicitudes de la interfaz" "HTTPS"
        sistema.apiGateway -> sistema.authService "Solicita validacion de identidad o sesion" "HTTPS/JSON"
        sistema.authService -> sistema.secretManager "Obtiene secretos autorizados" "Canal autenticado"
        sistema.apiGateway -> sistema.inventory "Enruta consultas y operaciones de inventario" "HTTPS/JSON"
        sistema.apiGateway -> sistema.orders "Enruta operaciones de pedidos" "HTTPS/JSON"
        sistema.apiGateway -> sistema.clients "Enruta operaciones de clientes" "HTTPS/JSON"
        sistema.apiGateway -> sistema.payments "Enruta operaciones de pagos" "HTTPS/JSON"
        sistema.payments -> sistema.secretManager "Obtiene credenciales autorizadas para integraciones" "Canal autenticado"
        sistema.orders -> sistema.inventory "Consulta y reserva stock, si corresponde" "HTTPS/JSON"
        sistema.orders -> sistema.payments "Solicita procesamiento de pago, si corresponde" "HTTPS/JSON"
        sistema.inventory -> sistema.dbInventory "Lee y escribe datos de inventario" "Acceso a datos"
        sistema.orders -> sistema.dbOrders "Lee y escribe pedidos" "Acceso a datos"
        sistema.clients -> sistema.dbClients "Lee y escribe perfiles de clientes" "Acceso a datos"
        sistema.payments -> sistema.dbPayments "Lee y escribe estados de pagos" "Acceso a datos"
        sistema.authService -> sistema.dbIdentity "Consulta y actualiza identidades" "Acceso a datos"
        sistema.apiGateway -> sistema.graphqlGateway "Enruta consultas GraphQL" "HTTPS/GraphQL"
        sistema.graphqlGateway -> sistema.inventory "Agrega informacion de productos y stock" "HTTPS/JSON"
        sistema.graphqlGateway -> sistema.orders "Agrega informacion autorizada de pedidos" "HTTPS/JSON"
        sistema.graphqlGateway -> sistema.clients "Consulta perfiles autorizados" "HTTPS/JSON"
        sistema.graphqlGateway -> sistema.authService "Comprueba contexto de identidad cuando aplica" "HTTPS/JSON"

        // Paso C3-1: relaciones internas y externas del API Gateway.
        sistema.frontend -> sistema.apiGateway.httpEntry "Invoca funciones del backend" "HTTPS"
        sistema.apiGateway.httpEntry -> sistema.apiGateway.identityFilter "Solicita comprobacion de acceso"
        sistema.apiGateway.identityFilter -> sistema.authService "Valida la identidad cuando corresponde" "HTTPS/JSON"
        sistema.apiGateway.identityFilter -> sistema.apiGateway.routeDispatcher "Permite una ruta publica o una solicitud autorizada"
        sistema.apiGateway.routeDispatcher -> sistema.inventory "Enruta operaciones de inventario" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.orders "Enruta operaciones de pedidos" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.clients "Enruta operaciones de clientes" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.payments "Enruta operaciones de pagos" "HTTPS/JSON"
        sistema.apiGateway.routeDispatcher -> sistema.graphqlGateway "Enruta consultas GraphQL" "HTTPS/GraphQL"
        sistema.apiGateway.routeDispatcher -> sistema.apiGateway.errorMapper "Reporta fallos de comunicacion y enrutamiento"


        // Paso C3-2: validacion y agregacion GraphQL.
        sistema.apiGateway -> sistema.graphqlGateway.graphqlEndpoint "Remite operaciones GraphQL" "HTTPS/GraphQL"
        sistema.graphqlGateway.graphqlEndpoint -> sistema.graphqlGateway.queryValidator "Verifica sintaxis, esquema y limites"
        sistema.graphqlGateway.queryValidator -> sistema.graphqlGateway.fieldAccess "Entrega consulta valida"
        sistema.graphqlGateway.fieldAccess -> sistema.authService "Comprueba permisos cuando procede" "HTTPS/JSON"
        sistema.graphqlGateway.fieldAccess -> sistema.graphqlGateway.resolvers "Autoriza campos y recursos"
        sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.serviceConnectors "Solicita informacion agregada"
        sistema.graphqlGateway.serviceConnectors -> sistema.inventory "Consulta productos y disponibilidad" "HTTPS/JSON"
        sistema.graphqlGateway.serviceConnectors -> sistema.orders "Consulta pedidos autorizados" "HTTPS/JSON"
        sistema.graphqlGateway.serviceConnectors -> sistema.clients "Consulta perfiles autorizados" "HTTPS/JSON"
        sistema.graphqlGateway.resolvers -> sistema.graphqlGateway.responseComposer "Envia datos y errores para componer respuesta"


        // Paso C3-3: componentes de identidad.
        sistema.apiGateway -> sistema.authService.identityApi "Valida identidad y sesiones" "HTTPS/JSON"
        sistema.graphqlGateway -> sistema.authService.identityApi "Consulta contexto autorizado cuando procede" "HTTPS/JSON"
        sistema.authService.identityApi -> sistema.authService.sessionManager "Gestiona sesion o token"
        sistema.authService.sessionManager -> sistema.authService.credentialsVerifier "Verifica identidad en autenticacion"
        sistema.authService.credentialsVerifier -> sistema.authService.identityRepo "Consulta registros permitidos"
        sistema.authService.identityRepo -> sistema.dbIdentity "Lee datos de identidad" "Acceso a datos"
        sistema.authService.sessionManager -> sistema.authService.secretsClient "Solicita material secreto autorizado"
        sistema.authService.secretsClient -> sistema.secretManager "Obtiene secretos de forma controlada" "Canal autenticado"


        // Paso C3-4: componentes de pedidos y persistencia.
        sistema.apiGateway -> sistema.orders.ordersApi "Enruta operaciones de pedidos" "HTTPS/JSON"
        sistema.graphqlGateway -> sistema.orders.ordersApi "Consulta pedidos permitidos" "HTTPS/JSON"
        sistema.orders.ordersApi -> sistema.orders.accessPolicy "Comprueba rol y propiedad del recurso"
        sistema.orders.accessPolicy -> sistema.orders.orderWorkflow "Encamina consultas de lectura autorizadas"
        sistema.orders.accessPolicy -> sistema.orders.idempotency "Autoriza la operacion de escritura"
        sistema.orders.idempotency -> sistema.orders.ordersRepo "Busca operacion previa por clave"
        sistema.orders.idempotency -> sistema.orders.orderWorkflow "Ejecuta solo la operacion admisible"
        sistema.orders.orderWorkflow -> sistema.orders.inventoryAdapter "Consulta o reserva disponibilidad"
        sistema.orders.orderWorkflow -> sistema.orders.paymentAdapter "Procesa o consulta pago cuando corresponde"
        sistema.orders.orderWorkflow -> sistema.orders.ordersRepo "Persiste cambio de estado"
        sistema.orders.inventoryAdapter -> sistema.inventory "Invoca contrato de inventario" "HTTPS/JSON"
        sistema.orders.paymentAdapter -> sistema.payments "Invoca contrato de pagos" "HTTPS/JSON"
        sistema.orders.ordersRepo -> sistema.dbOrders "Lee y escribe pedidos y claves" "Acceso a datos"


        // Paso 4: respuestas explicitas que se desean seguir en escenarios dinamicos.
        // Son relaciones de comunicacion: no representan aprobacion de pruebas.
        sistema.dbInventory -> sistema.inventory "Devuelve resultados de consulta" "Acceso a datos"
        sistema.inventory -> sistema.apiGateway "Responde consultas de inventario" "HTTPS/JSON"
        sistema.apiGateway -> sistema.frontend "Devuelve respuestas y errores controlados" "HTTPS"
        sistema.frontend -> visitante "Presenta resultados de consulta" "Interfaz web"
        sistema.frontend -> cliente "Presenta resultados y errores de las operaciones" "Interfaz web"
        sistema.dbOrders -> sistema.orders "Devuelve estado de pedidos y operaciones" "Acceso a datos"
        sistema.orders -> sistema.apiGateway "Responde operaciones y consultas de pedidos" "HTTPS/JSON"
        sistema.authService -> sistema.apiGateway "Responde comprobaciones de identidad" "HTTPS/JSON"
        sistema.inventory -> sistema.orders "Responde consultas de disponibilidad" "HTTPS/JSON"
        sistema.payments -> sistema.orders "Responde resultado de operaciones de pago" "HTTPS/JSON"
        sistema.graphqlGateway -> sistema.apiGateway "Devuelve resultado agregado o error" "HTTPS/GraphQL"
        sistema.inventory -> sistema.graphqlGateway "Devuelve productos y disponibilidad" "HTTPS/JSON"
        sistema.orders -> sistema.graphqlGateway "Devuelve datos autorizados de pedidos" "HTTPS/JSON"
        sistema.clients -> sistema.graphqlGateway "Devuelve informacion autorizada del cliente" "HTTPS/JSON"
        sistema.graphqlGateway.queryValidator -> sistema.graphqlGateway.graphqlEndpoint "Reporta rechazo de consulta invalida"
        sistema.graphqlGateway.graphqlEndpoint -> sistema.apiGateway "Responde error GraphQL de validacion" "HTTPS/GraphQL"
        sistema.orders.ordersRepo -> sistema.orders.idempotency "Devuelve resultado de operacion previamente registrada"
        sistema.orders.idempotency -> sistema.orders.ordersApi "Devuelve resultado existente sin procesar de nuevo"
        sistema.orders.ordersApi -> sistema.apiGateway "Devuelve respuesta controlada de pedidos" "HTTPS/JSON"

        // PASO 5 - ENTORNO DE PRUEBAS (modelo ilustrativo, no despliegue comprobado).
        pruebas = deploymentEnvironment "Pruebas_Integradas" {
            // Navegador: en este ejemplo el frontend es una SPA ejecutada en el cliente.
            deploymentNode "Dispositivo del usuario" "Equipo con navegador web para ejecutar el frontend responsivo." "Equipo cliente" {
                tags "ZonaCliente"
                deploymentNode "Navegador web" "Runtime JavaScript del frontend; no es un servidor backend." "Navegador" {
                    containerInstance sistema.frontend
                }
            }
            // Zona de entrada (no implica por si sola un firewall instalado).
            deploymentNode "Infraestructura de pruebas" "Agrupacion logica de los nodos del entorno de pruebas." "Entorno de pruebas" {
                tags "ZonaEntorno"
                deploymentNode "Zona de entrada" "Ubicacion del acceso HTTP(S) hacia el backend." "Segmento de acceso" {
                    tags "ZonaPublica"
                    deploymentNode "Host de entrada" "Nodo que ejecuta API Gateway para las pruebas." "Servidor de aplicaciones" {
                        containerInstance sistema.apiGateway
                    }
                }
                deploymentNode "Zona de servicios privados" "Segmento logico no expuesto directamente a los clientes." "Segmento privado" {
                    tags "ZonaPrivada"
                    deploymentNode "Host de servicios" "Ejecuta los servicios internos de la plataforma." "Host de aplicaciones" {
                        containerInstance sistema.authService
                        containerInstance sistema.graphqlGateway
                        containerInstance sistema.inventory
                        containerInstance sistema.orders
                        containerInstance sistema.clients
                        containerInstance sistema.payments
                    }
                }
                deploymentNode "Zona de datos" "Almacenes accesibles solo por las aplicaciones autorizadas." "Segmento de datos" {
                    tags "ZonaDatos"
                    deploymentNode "Host de persistencia" "Almacenes logicos; pueden residir en un solo motor o en motores separados." "Servicio de datos" {
                        containerInstance sistema.dbInventory
                        containerInstance sistema.dbOrders
                        containerInstance sistema.dbClients
                        containerInstance sistema.dbPayments
                        containerInstance sistema.dbIdentity
                    }
                }
                deploymentNode "Zona de secretos" "Servicio de secretos del entorno de pruebas." "Segmento protegido" {
                    tags "ZonaSecretos"
                    deploymentNode "Host del gestor de secretos" "Servicio de gestion de secretos, no visible directamente desde el navegador." "Servicio protegido" {
                        containerInstance sistema.secretManager
                    }
                }
            }
        }

        // Variante local: todos los procesos en una misma maquina fisica.
        // La jerarquia de nodos organiza procesos, pero no demuestra aislamiento de red.
        local = deploymentEnvironment "Desarrollo_Local" {
            deploymentNode "Equipo de desarrollo" "Estacion local usada para pruebas y restauracion de datos." "Estacion de trabajo" {
                tags "ZonaLocal"
                deploymentNode "Navegador local" "Frontend SPA ejecutado en el navegador." "Navegador" {
                    containerInstance sistema.frontend
                }
                deploymentNode "Proceso de entrada" "API Gateway local, expuesto por puerto de desarrollo." "Proceso local" {
                    containerInstance sistema.apiGateway
                }
                deploymentNode "Procesos privados" "Servicios internos; pueden utilizar procesos o contenedores de runtime." "Procesos locales" {
                    containerInstance sistema.authService
                    containerInstance sistema.graphqlGateway
                    containerInstance sistema.inventory
                    containerInstance sistema.orders
                    containerInstance sistema.clients
                    containerInstance sistema.payments
                }
                deploymentNode "Persistencia y secretos locales" "Servicios de desarrollo con datos ficticios y secretos de prueba." "Servicios locales" {
                    containerInstance sistema.dbInventory
                    containerInstance sistema.dbOrders
                    containerInstance sistema.dbClients
                    containerInstance sistema.dbPayments
                    containerInstance sistema.dbIdentity
                    containerInstance sistema.secretManager
                }
            }
        }
    }

    views {
        systemContext sistema "C1_Contexto" "Contexto de negocio: actores y dependencias externas." {
            title "C1 - Contexto de la Heladeria"
            include *
            autoLayout lr
        }

        container sistema "C2_Contenedores" "Aplicaciones y almacenes de datos de la Heladeria." {
            title "C2 - Contenedores de la Heladeria"
            include *
            autoLayout lr
        }

        // Vistas adicionales: son recortes del mismo modelo, NO otros sistemas.
        container sistema "C2_Catalogo" "Recorrido estructural relacionado con la consulta de catalogo." {
            include visitante cliente sistema.frontend sistema.apiGateway sistema.authService sistema.inventory sistema.dbInventory
            autoLayout lr
        }

        container sistema "C2_Pedidos" "Recorrido estructural relacionado con el registro de pedidos." {
            include cliente sistema.frontend sistema.apiGateway sistema.authService sistema.orders sistema.inventory sistema.payments sistema.dbOrders sistema.dbInventory sistema.dbPayments
            autoLayout lr
        }


        component sistema.apiGateway "C3_API_Gateway" "Componentes internos del punto de entrada HTTP." {
            title "C3 - API Gateway"
            include *
            autoLayout lr
        }


        component sistema.graphqlGateway "C3_GraphQL" "Validacion, autorizacion y agregacion de datos." {
            title "C3 - GraphQL Gateway"
            include *
            autoLayout lr
        }


        component sistema.authService "C3_Auth_Service" "Identidad, sesiones, credenciales y secretos." {
            title "C3 - Auth Service"
            include *
            autoLayout lr
        }


        component sistema.orders "C3_Orders" "Autorizacion, idempotencia, logica y persistencia de pedidos." {
            title "C3 - orders"
            include *
            autoLayout lr
        }


        // ================================================
        // PASO 4 - VISTAS DINAMICAS (COMPLEMENTARIAS A C4)
        // ================================================

        dynamic sistema "D_F01_Exito" "Lectura E2E desde el navegador hasta inventario y regreso." {
            title "F01 - Consulta de catalogo: exito"
            1: visitante -> sistema.frontend "Abre el catalogo de helados"
            2: sistema.frontend -> sistema.apiGateway "GET /productos con traceId ficticio" "HTTPS"
            3: sistema.apiGateway -> sistema.inventory "Consulta el catalogo" "HTTPS/JSON"
            4: sistema.inventory -> sistema.dbInventory "Busca productos publicados" "Acceso a datos"
            5: sistema.dbInventory -> sistema.inventory "Devuelve registros de prueba" "Acceso a datos"
            6: sistema.inventory -> sistema.apiGateway "Responde productos disponibles" "HTTPS/JSON"
            7: sistema.apiGateway -> sistema.frontend "Devuelve listado y estado" "HTTPS"
            8: sistema.frontend -> visitante "Presenta productos o estado sin resultados"
            autoLayout lr
        }

        dynamic sistema "D_F01_Recuperacion" "Indisponibilidad de inventario, mensaje comprensible y nuevo intento tras restauracion." {
            title "F01 - Fallo controlado y recuperacion"
            1: visitante -> sistema.frontend "Abre catalogo"
            2: sistema.frontend -> sistema.apiGateway "GET /productos" "HTTPS"
            3: sistema.apiGateway -> sistema.inventory "Consulta catalogo; dependencia no responde" "HTTPS/JSON"
            4: sistema.apiGateway -> sistema.frontend "Timeout detectado: error controlado" "HTTPS"
            5: sistema.frontend -> visitante "Muestra error sin presentar datos falsos"
            6: visitante -> sistema.frontend "Reintenta tras restaurar la dependencia"
            7: sistema.frontend -> sistema.apiGateway "Reintenta GET /productos" "HTTPS"
            8: sistema.apiGateway -> sistema.inventory "Consulta catalogo recuperado" "HTTPS/JSON"
            9: sistema.inventory -> sistema.dbInventory "Busca productos publicados" "Acceso a datos"
            10: sistema.dbInventory -> sistema.inventory "Devuelve productos" "Acceso a datos"
            11: sistema.inventory -> sistema.apiGateway "Responde listado" "HTTPS/JSON"
            12: sistema.apiGateway -> sistema.frontend "Devuelve listado" "HTTPS"
            13: sistema.frontend -> visitante "Muestra productos recuperados"
            autoLayout lr
        }

        dynamic sistema "D_F02_Exito" "Cambio de estado con validacion de identidad, dependencias, persistencia y respuesta." {
            title "F02 - Registro de pedido: exito"
            1: cliente -> sistema.frontend "Confirma pedido de helados ficticio"
            2: sistema.frontend -> sistema.apiGateway "POST /pedidos; clave de idempotencia" "HTTPS"
            3: sistema.apiGateway -> sistema.authService "Verifica identidad de sesion" "HTTPS/JSON"
            4: sistema.authService -> sistema.apiGateway "Confirma identidad valida" "HTTPS/JSON"
            5: sistema.apiGateway -> sistema.orders "Solicita registrar pedido" "HTTPS/JSON"
            6: sistema.orders -> sistema.inventory "Verifica o reserva stock segun contrato" "HTTPS/JSON"
            7: sistema.inventory -> sistema.orders "Comunica resultado de stock" "HTTPS/JSON"
            8: sistema.orders -> sistema.payments "Procesa pago cuando aplica" "HTTPS/JSON"
            9: sistema.payments -> sistema.orders "Comunica resultado de pago" "HTTPS/JSON"
            10: sistema.orders -> sistema.dbOrders "Persiste pedido, estado y clave" "Acceso a datos"
            11: sistema.dbOrders -> sistema.orders "Confirma escritura verificada" "Acceso a datos"
            12: sistema.orders -> sistema.apiGateway "Devuelve identificador y estado" "HTTPS/JSON"
            13: sistema.apiGateway -> sistema.frontend "Responde operacion" "HTTPS"
            14: sistema.frontend -> cliente "Muestra resultado verificable"
            autoLayout lr
        }

        dynamic sistema "D_F02_Reintento" "Segunda ejecucion con la misma clave de operacion; devuelve resultado existente." {
            title "F02 - Reintento de pedido: sin duplicacion"
            1: cliente -> sistema.frontend "Reintenta el mismo pedido tras respuesta incierta"
            2: sistema.frontend -> sistema.apiGateway "POST /pedidos con la misma clave" "HTTPS"
            3: sistema.apiGateway -> sistema.orders "Remite solicitud repetida" "HTTPS/JSON"
            4: sistema.orders -> sistema.dbOrders "Consulta clave y resultado previo" "Acceso a datos"
            5: sistema.dbOrders -> sistema.orders "Devuelve pedido ya registrado" "Acceso a datos"
            6: sistema.orders -> sistema.apiGateway "Reutiliza resultado: no crea segundo pedido" "HTTPS/JSON"
            7: sistema.apiGateway -> sistema.frontend "Devuelve identificador previo" "HTTPS"
            8: sistema.frontend -> cliente "Muestra pedido existente"
            autoLayout lr
        }

        dynamic sistema.orders "D_F02_Idempotencia_C3" "Detalle de una solicitud repetida al interior del servicio orders." {
            title "F02 - Idempotencia: componentes internos"
            1: sistema.apiGateway -> sistema.orders.ordersApi "Entrega POST repetido y clave" "HTTPS/JSON"
            2: sistema.orders.ordersApi -> sistema.orders.accessPolicy "Verifica rol y permisos"
            3: sistema.orders.accessPolicy -> sistema.orders.idempotency "Permite escritura autorizada"
            4: sistema.orders.idempotency -> sistema.orders.ordersRepo "Busca clave y huella de operacion"
            5: sistema.orders.ordersRepo -> sistema.dbOrders "Consulta operacion ya persistida" "Acceso a datos"
            6: sistema.orders.ordersRepo -> sistema.orders.idempotency "Entrega resultado existente"
            7: sistema.orders.idempotency -> sistema.orders.ordersApi "Retorna resultado sin ejecutar el workflow"
            8: sistema.orders.ordersApi -> sistema.apiGateway "Devuelve mismo pedido, sin duplicar" "HTTPS/JSON"
            autoLayout lr
        }

        dynamic sistema "D_F03_Propio" "Lectura autorizada con identidad vigente y comprobacion de datos." {
            title "F03 - Consulta protegida: pedido propio"
            1: cliente -> sistema.frontend "Abre un pedido propio"
            2: sistema.frontend -> sistema.apiGateway "GET /pedidos/id" "HTTPS"
            3: sistema.apiGateway -> sistema.authService "Comprueba sesion" "HTTPS/JSON"
            4: sistema.authService -> sistema.apiGateway "Sesion valida" "HTTPS/JSON"
            5: sistema.apiGateway -> sistema.orders "Solicita pedido con contexto de usuario" "HTTPS/JSON"
            6: sistema.orders -> sistema.dbOrders "Consulta pedido filtrado por titular" "Acceso a datos"
            7: sistema.dbOrders -> sistema.orders "Devuelve pedido del titular" "Acceso a datos"
            8: sistema.orders -> sistema.apiGateway "Responde datos autorizados" "HTTPS/JSON"
            9: sistema.apiGateway -> sistema.frontend "Devuelve pedido" "HTTPS"
            10: sistema.frontend -> cliente "Muestra identificador y estado"
            autoLayout lr
        }

        dynamic sistema "D_F03_Ajeno" "Prueba negativa de autorizacion por pertenencia del recurso." {
            title "F03 - Consulta protegida: recurso ajeno"
            1: cliente -> sistema.frontend "Intenta abrir pedido de otro cliente"
            2: sistema.frontend -> sistema.apiGateway "GET /pedidos/idAjeno" "HTTPS"
            3: sistema.apiGateway -> sistema.authService "Comprueba sesion" "HTTPS/JSON"
            4: sistema.authService -> sistema.apiGateway "Sesion valida (no implica acceso al pedido)" "HTTPS/JSON"
            5: sistema.apiGateway -> sistema.orders "Consulta recurso usando identidad" "HTTPS/JSON"
            6: sistema.orders -> sistema.dbOrders "Consulta con filtro por titular" "Acceso a datos"
            7: sistema.dbOrders -> sistema.orders "No encuentra recurso autorizado" "Acceso a datos"
            8: sistema.orders -> sistema.apiGateway "Rechaza o no revela recurso ajeno" "HTTPS/JSON"
            9: sistema.apiGateway -> sistema.frontend "Entrega error conforme al contrato" "HTTPS"
            10: sistema.frontend -> cliente "Muestra rechazo sin datos ajenos"
            autoLayout lr
        }

        dynamic sistema "D_F03_Expirada" "El gateway rechaza la solicitud antes de acceder al subsistema protegido." {
            title "F03 - Sesion expirada: rechazo temprano"
            1: cliente -> sistema.frontend "Intenta consultar pedido con sesion expirada"
            2: sistema.frontend -> sistema.apiGateway "GET /pedidos/id con sesion expirada" "HTTPS"
            3: sistema.apiGateway -> sistema.authService "Verifica sesion" "HTTPS/JSON"
            4: sistema.authService -> sistema.apiGateway "Identidad no valida: sesion expirada" "HTTPS/JSON"
            5: sistema.apiGateway -> sistema.frontend "Responde rechazo de autenticacion" "HTTPS"
            6: sistema.frontend -> cliente "Solicita nueva autenticacion sin mostrar pedido"
            autoLayout lr
        }

        dynamic sistema "D_F04_GraphQL_Exito" "La pantalla presenta informacion combinada de pedidos y productos." {
            title "F04 - GraphQL: agregacion exitosa"
            1: cliente -> sistema.frontend "Abre vista combinada de pedidos y productos"
            2: sistema.frontend -> sistema.apiGateway "POST /graphql con consulta permitida" "HTTPS"
            3: sistema.apiGateway -> sistema.graphqlGateway "Entrega consulta y contexto de acceso" "HTTPS/GraphQL"
            4: sistema.graphqlGateway -> sistema.inventory "Consulta productos y disponibilidad" "HTTPS/JSON"
            4: sistema.graphqlGateway -> sistema.orders "Consulta pedidos autorizados" "HTTPS/JSON"
            5: sistema.inventory -> sistema.graphqlGateway "Devuelve datos de catalogo" "HTTPS/JSON"
            5: sistema.orders -> sistema.graphqlGateway "Devuelve pedidos permitidos" "HTTPS/JSON"
            6: sistema.graphqlGateway -> sistema.apiGateway "Compone respuesta agregada" "HTTPS/GraphQL"
            7: sistema.apiGateway -> sistema.frontend "Entrega resultado autorizado" "HTTPS"
            8: sistema.frontend -> cliente "Muestra datos agregados desde dos servicios"
            autoLayout lr
        }

        dynamic sistema "D_F04_GraphQL_Parcial" "No se presenta una respuesta parcial como informacion completa." {
            title "F04 - GraphQL: dependencia fallida"
            1: cliente -> sistema.frontend "Consulta vista agregada"
            2: sistema.frontend -> sistema.apiGateway "POST /graphql" "HTTPS"
            3: sistema.apiGateway -> sistema.graphqlGateway "Remite consulta permitida" "HTTPS/GraphQL"
            4: sistema.graphqlGateway -> sistema.inventory "Consulta catalogo" "HTTPS/JSON"
            4: sistema.graphqlGateway -> sistema.orders "Consulta pedidos (se induce fallo)" "HTTPS/JSON"
            5: sistema.inventory -> sistema.graphqlGateway "Devuelve catalogo" "HTTPS/JSON"
            5: sistema.orders -> sistema.graphqlGateway "Devuelve error controlado" "HTTPS/JSON"
            6: sistema.graphqlGateway -> sistema.apiGateway "Entrega error o respuesta parcial identificada" "HTTPS/GraphQL"
            7: sistema.apiGateway -> sistema.frontend "Transmite estado de error" "HTTPS"
            8: sistema.frontend -> cliente "Informa resultado incompleto o falla"
            autoLayout lr
        }

        dynamic sistema.graphqlGateway "D_F04_GraphQL_Limite_C3" "Rechazo antes de ejecutar resolvers o consultar servicios privados." {
            title "F04 - GraphQL: consulta excede limite"
            1: sistema.apiGateway -> sistema.graphqlGateway.graphqlEndpoint "Envia consulta que supera el limite" "HTTPS/GraphQL"
            2: sistema.graphqlGateway.graphqlEndpoint -> sistema.graphqlGateway.queryValidator "Calcula limite configurado"
            3: sistema.graphqlGateway.queryValidator -> sistema.graphqlGateway.graphqlEndpoint "Rechaza consulta excesiva"
            4: sistema.graphqlGateway.graphqlEndpoint -> sistema.apiGateway "Devuelve error sin llamar a resolvers" "HTTPS/GraphQL"
            autoLayout lr
        }


        // PASO 5 - VISTAS DE DESPLIEGUE.
        deployment sistema pruebas "DEP_Pruebas" "Ubicacion de las aplicaciones y datos en el entorno de pruebas." {
            title "Despliegue - Pruebas integradas (referencia)"
            include *
            autoLayout lr
        }

        deployment sistema local "DEP_Local" "Todos los servicios del caso en un equipo local." {
            title "Despliegue - Desarrollo local"
            include *
            autoLayout lr
        }
        styles {
            // PASO 5 - ESTILOS DE DESPLIEGUE.
            element "Deployment Node" {
                background #E9EFF5
                color #213F56
                stroke #8FA5B7
            }
            element "Infrastructure Node" {
                shape roundedbox
                background #EDF0F3
                color #334454
            }
            element "ZonaCliente" {
                background #F1F5F9
                color #173B5D
            }
            element "ZonaEntorno" {
                background #F4F6F8
                color #213F56
            }
            element "ZonaPublica" {
                background #DCEAF7
                color #173B5D
            }
            element "ZonaPrivada" {
                background #E5EEE8
                color #20513D
            }
            element "ZonaDatos" {
                background #ECEAF2
                color #463D64
            }
            element "ZonaSecretos" {
                background #EEE5E1
                color #68483C
            }
            element "ZonaLocal" {
                background #F0F3F6
                color #243F56
            }
            element "Person" {
                shape person
                background #56718A
                color #FFFFFF
            }
            element "Software System" {
                shape roundedbox
                background #0C527A
                color #FFFFFF
            }
            element "SistemaEvaluado" {
                background #173B5D
                color #FFFFFF
            }
            element "Container" {
                shape roundedbox
                background #E3ECF5
                color #173B5D
            }
            element "Frontend" {
                shape webbrowser
                background #CDE5F7
                color #153E5B
            }
            element "Gateway" {
                background #2B6289
                color #FFFFFF
            }
            element "Seguridad" {
                background #3F6171
                color #FFFFFF
            }
            element "Privado" {
                background #D5E8EF
                color #173B5D
            }
            element "BaseDatos" {
                shape cylinder
                background #E5EAF0
                color #243F56
            }
            element "SistemaExterno" {
                background #F1EDE7
                color #544633
                stroke #A89D8A
            }
            element "Analitica" {
                background #E7E0F2
                color #453166
            }

            // C3: colores funcionales para componentes internos.
            element "Component" {
                shape roundedbox
                background #EDF3F7
                color #173B5D
            }
            element "EntradaC3" {
                background #D3E9F7
                color #153F62
            }
            element "ControlC3" {
                background #DBE4EC
                color #213F56
            }
            element "AplicacionC3" {
                background #D7E9DE
                color #20533E
            }
            element "IntegracionC3" {
                background #E9E2F2
                color #4A3666
            }
            element "PersistenciaC3" {
                background #E9EBEE
                color #334454
            }
            element "ErrorC3" {
                background #F2E6DB
                color #70462C
            }
            relationship "Relationship" {
                color #60758A
                thickness 2
            }
        }
    }
}
