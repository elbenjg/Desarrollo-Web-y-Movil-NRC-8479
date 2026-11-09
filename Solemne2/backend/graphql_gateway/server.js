// GraphQL Gateway privado de Frío Natural.
const crypto = require('crypto');
const express = require('express');
const {
    ApolloServer,
    gql,
    ApolloError,
    ForbiddenError,
    UserInputError,
} = require('apollo-server-express');
const { GraphQLError } = require('graphql');

function requerirEnv(nombre) {
    const valor = process.env[nombre];
    if (!valor) throw new Error(`${nombre} no está configurado`);
    return valor;
}

const SECRETO = requerirEnv('GRAPHQL_SECRET');
const SECRETOS = {
    orders: requerirEnv('ORDERS_SECRET'),
    inventory: requerirEnv('INVENTORY_SECRET'),
    payments: requerirEnv('PAYMENTS_SECRET'),
    analytics: requerirEnv('ANALYTICS_SECRET'),
};
const URLS = {
    orders: process.env.ORDERS_URL || 'http://127.0.0.1:8002',
    inventory: process.env.INVENTORY_URL || 'http://127.0.0.1:8001',
    payments: process.env.PAYMENTS_URL || 'http://127.0.0.1:8004',
    analytics: process.env.ANALYTICS_URL || 'http://127.0.0.1:8006',
};
const STAFF = ['admin', 'dueno', 'cajero', 'despacho'];
const MAX_PROFUNDIDAD = 5;
const MAX_CAMPOS = 150;
const MAX_POR_PAGINA = 20;
const PLAZO_MS = 3000;

const typeDefs = gql`
    type Producto {
        id: Int!
        nombre: String!
        categoria: String!
        imagen: String
        disponible: Boolean!
    }

    type ItemPedido {
        productoId: Int!
        nombre: String!
        precioUnitario: Int!
        cantidad: Int!
        subtotal: Int!
        producto: Producto
    }

    type Envio {
        direccion: String!
        comuna: String!
        provincia: String!
        region: String!
    }

    type Pago {
        id: ID!
        estado: String!
        metodo: String!
        monto: Int!
    }

    type ResumenPedido {
        id: ID!
        estado: String!
        total: Int!
        creado: String!
        motivoAnulacion: String
        items: [ItemPedido!]!
        envio: Envio
        pagos: [Pago!]
        clienteId: String
    }

    type PaginaPedidos {
        total: Int!
        pagina: Int!
        porPagina: Int!
        pedidos: [ResumenPedido!]!
    }

    type VentaProducto {
        productoId: Int!
        nombre: String!
        categoria: String
        cantidad: Int!
        monto: Int!
    }

    type ReporteVentas {
        desde: String!
        hasta: String!
        totalVentas: Int!
        cantidadPedidos: Int!
        porProducto: [VentaProducto!]!
    }

    type Query {
        resumenPedido(id: ID!): ResumenPedido
        pedidos(pagina: Int = 1, porPagina: Int = 10, estado: String): PaginaPedidos!
        reporteVentas(desde: String!, hasta: String!): ReporteVentas!
    }
`;

async function llamar(servicio, ruta, ctx) {
    let resp;
    try {
        resp = await fetch(URLS[servicio] + ruta, {
            headers: {
                'X-Internal-Secret': SECRETOS[servicio],
                'X-User-Id': ctx.userId,
                'X-User-Roles': ctx.roles.join(','),
                'X-Correlation-Id': ctx.cid,
            },
            signal: AbortSignal.timeout(PLAZO_MS),
        });
    } catch (e) {
        throw new ApolloError(
            `Servicio ${servicio} no disponible`,
            'SERVICE_UNAVAILABLE',
        );
    }
    if (resp.status === 404) return null;
    if (resp.status === 400 || resp.status === 422)
        throw new UserInputError('Parámetros inválidos');
    if (resp.status === 401 || resp.status === 403)
        throw new ForbiddenError('No autorizado');
    if (!resp.ok)
        throw new ApolloError(
            `Servicio ${servicio} respondió ${resp.status}`,
            'UPSTREAM_ERROR',
        );
    return resp.json();
}

function crearCargadorProductos(ctx) {
    const cache = new Map();
    let pendientes = new Set();
    let lote = null;
    return (id) => {
        if (cache.has(id)) return cache.get(id);
        pendientes.add(id);
        if (!lote) {
            lote = new Promise((r) => setImmediate(r)).then(async () => {
                const ids = [...pendientes];
                pendientes = new Set();
                lote = null;
                console.log(`cid=${ctx.cid} inventory lote ids=${ids.join(',')}`);
                const lista =
                    (await llamar(
                        'inventory',
                        `/products?ids=${ids.join(',')}`,
                        ctx,
                    )) || [];
                return new Map(lista.map((p) => [p.id, p]));
            });
        }
        const promesa = lote.then((mapa) => mapa.get(id) || null);
        cache.set(id, promesa);
        return promesa;
    };
}

const esStaff = (ctx) => ctx.roles.some((r) => STAFF.includes(r));

const resolvers = {
    Query: {
        async resumenPedido(obj, { id }, ctx) {
            if (!/^[A-Za-z0-9_-]{1,40}$/.test(id))
                throw new UserInputError('id inválido');
            return llamar('orders', `/orders/${id}`, ctx);
        },
        async pedidos(obj, { pagina, porPagina, estado }, ctx) {
            if (pagina < 1 || porPagina < 1 || porPagina > MAX_POR_PAGINA) {
                throw new UserInputError(
                    `pagina >= 1 y porPagina entre 1 y ${MAX_POR_PAGINA}`,
                );
            }
            const params = new URLSearchParams({
                skip: (pagina - 1) * porPagina,
                limit: porPagina,
            });
            if (estado) params.set('estado', estado);
            const res = await llamar('orders', `/orders?${params}`, ctx);
            return { total: res.total, pagina, porPagina, pedidos: res.pedidos };
        },
        async reporteVentas(obj, { desde, hasta }, ctx) {
            if (!['dueno', 'admin'].some((r) => ctx.roles.includes(r)))
                throw new ForbiddenError('Reporte restringido');
            const params = new URLSearchParams({ desde, hasta });
            return llamar('analytics', `/reports/sales?${params}`, ctx);
        },
    },
    ResumenPedido: {
        motivoAnulacion: (p) => p.motivo_anulacion,
        envio(p, args, ctx) {
            if (
                esStaff(ctx) &&
                !['admin', 'despacho'].some((r) => ctx.roles.includes(r))
            ) {
                throw new ForbiddenError('Campo envio restringido para tu rol');
            }
            return p.envio || null;
        },
        clienteId(p, args, ctx) {
            if (!esStaff(ctx))
                throw new ForbiddenError('Campo clienteId restringido al personal');
            return p.user_id;
        },
        pagos: (p, args, ctx) =>
            llamar('payments', `/payments?order_id=${encodeURIComponent(p.id)}`, ctx),
    },
    ItemPedido: {
        productoId: (i) => i.product_id,
        precioUnitario: (i) => i.precio_unitario,
        producto: (i, args, ctx) => ctx.cargarProducto(i.product_id),
    },
    ReporteVentas: {
        totalVentas: (r) => r.total_ventas,
        cantidadPedidos: (r) => r.cantidad_pedidos,
        porProducto: (r) => r.por_producto,
    },
    VentaProducto: {
        productoId: (v) => v.product_id,
        categoria: async (v, args, ctx) => {
            const producto = await ctx.cargarProducto(v.product_id);
            return producto ? producto.categoria : null;
        },
    },
};

function medir(selectionSet, context, nivel, acumulado) {
    if (
        !selectionSet ||
        nivel > MAX_PROFUNDIDAD + 1 ||
        acumulado.campos > MAX_CAMPOS
    )
        return nivel;
    let maximo = nivel;
    for (const sel of selectionSet.selections) {
        acumulado.campos += 1;
        const hijo =
            sel.kind === 'FragmentSpread'
                ? (context.getFragment(sel.name.value) || {}).selectionSet
                : sel.selectionSet;
        const siguiente = sel.kind === 'Field' ? nivel + 1 : nivel;
        maximo = Math.max(maximo, medir(hijo, context, siguiente, acumulado));
    }
    return maximo;
}

function limiteCosto(context) {
    return {
        OperationDefinition(node) {
            const acumulado = { campos: 0 };
            const profundidad = medir(node.selectionSet, context, 0, acumulado);
            if (profundidad > MAX_PROFUNDIDAD) {
                context.reportError(
                    new GraphQLError(
                        `Consulta demasiado profunda (máximo ${MAX_PROFUNDIDAD})`,
                        [node],
                    ),
                );
            }
            if (acumulado.campos > MAX_CAMPOS) {
                context.reportError(
                    new GraphQLError(
                        `Consulta demasiado costosa (máximo ${MAX_CAMPOS} campos)`,
                        [node],
                    ),
                );
            }
        },
    };
}

function iguales(a, b) {
    const ha = crypto.createHash('sha256').update(a).digest();
    const hb = crypto.createHash('sha256').update(b).digest();
    return crypto.timingSafeEqual(ha, hb);
}

const app = express();

app.use((req, res, next) => {
    const cid = /^[A-Za-z0-9-]{8,64}$/.test(req.get('x-correlation-id') || '')
        ? req.get('x-correlation-id')
        : crypto.randomUUID();
    const inicio = Date.now();
    res.on('finish', () =>
        console.log(
            `cid=${cid} ${req.method} ${req.path} -> ${res.statusCode} (${Date.now() - inicio} ms)`,
        ),
    );
    req.cid = cid;
    if (!iguales(req.get('x-internal-secret') || '', SECRETO)) {
        return res.status(403).json({ detail: 'Solicitud no autorizada' });
    }
    next();
});

app.get('/health', (req, res) =>
    res.json({ status: 'ok', service: 'graphql-gateway' }),
);

app.use('/graphql', (req, res, next) => {
    if (!req.get('x-user-id'))
        return res.status(401).json({ detail: 'Sesión requerida' });
    next();
});

async function startServer() {
    const apolloServer = new ApolloServer({
        typeDefs,
        resolvers,
        introspection: false,
        allowBatchedHttpRequests: false,
        validationRules: [limiteCosto],
        context: ({ req }) => {
            const ctx = {
                userId: req.get('x-user-id'),
                roles: (req.get('x-user-roles') || '').split(',').filter(Boolean),
                cid: req.cid,
            };
            ctx.cargarProducto = crearCargadorProductos(ctx);
            return ctx;
        },
        formatError: (err) => ({
            message: err.message,
            path: err.path,
            extensions: { code: err.extensions && err.extensions.code },
        }),
    });
    await apolloServer.start();
    apolloServer.applyMiddleware({
        app,
        path: '/graphql',
        cors: false,
        bodyParserConfig: { limit: '10kb' },
    });
    app.use((err, req, res, next) => {
        const codigo = err.status || 500;
        console.error(`cid=${req.cid} ${err.message}`);
        res.status(codigo).json({
            detail: codigo < 500 ? 'Solicitud GraphQL inválida' : 'Error interno',
        });
    });
    const puerto = Number(process.env.PORT || 8005);
    app.listen(puerto, '127.0.0.1', () =>
        console.log(`GraphQL Gateway privado en http://127.0.0.1:${puerto}/graphql`),
    );
}

startServer();
