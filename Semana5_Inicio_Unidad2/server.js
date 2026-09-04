const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors'); // Revisa si como cliente tengo certificado de seguridad. Y al revés el servidor.

const {ApolloServer, gql} = require('apollo-server-express'); 
const Usuario = require('./models/usuario');
const Admin = require('./models/admin');
const Cajero = require('./models/cajero');

mongoose.connect('mongodb://localhost:27017/semana5db'); // Para conectarse a la base de datos de MongoDB.
const typeDefs = gql`
    type Usuario { #Creación tipo Usuario. 
        id: ID!
        nombre: String!
        pass: String!
        rut: String!
        direccion: String!
        comuna: String!
        provincia: String!
        region: String!
        fnac: String!
        sexo: String!
        telefono: String!
        correo: String!
        correoValidado: Boolean!
        rol: String!
    }
        
    input UsuarioInput { # Input para crear un usuario.
        nombre: String!
        pass: String!
        rut: String!
        direccion: String!
        comuna: String!
        provincia: String!
        region: String!
        fnac: String!
        sexo: String!
        telefono: String!
        correo: String!
    }
        
    type Admin{ # Creación tipo Admin.
        id: ID!
        nombre: String!
        pass: String!
        rol: String!
    }
        
    input AdminInput{ # Input para crear un admin.
        nombre: String!
        pass: String!
    }

    type Cajero{ # Creación tipo Cajero.
        id: ID!
        nombre: String!
        pass: String!
        rol: String!
    }
    
    input CajeroInput{ # Input para crear un cajero.
        nombre: String!     
        pass: String!
    }
        
    type Alert{ # Para que avise si se borró algo. 
        message: String!
    }

    type Query {   # Para consultas
        getUsuarios: [Usuario]
        getUsuarioById(id: ID!): Usuario
        getUsuarioByRut(rut: String!): Usuario
        getUsuarioByCorreo(correo: String!): Usuario
        getAdmins: [Admin]
        getCajeros: [Cajero]
    }

    type Mutation { # Para crear, actualizar y borrar.
        addUsuario(input: UsuarioInput): Usuario
        updUsuario(id: ID!, input: UsuarioInput): Usuario
        delUsuario(id: ID!): Alert
        addAdmin(input: AdminInput): Admin
        addCajero(input: CajeroInput): Cajero
    }
`;

const resolvers = {
    Query: {
        async getUsuarios(obj) {
            const usuario = await Usuario.find();
            return usuario;
        },
        async getUsuarioById(obj, {id}) {
            const usuarioBus = await Usuario.findById(id);
            if (usuarioBus == null) {
                return null; 
            } else{
                return usuarioBus;
            }
        },
        async getAdmins(obj) {
            const admin = await Admin.find();
            return admin;
        },
        async getCajeros(obj) {
            const cajero = await Cajero.find();
            return cajero;
        }
    },
    Mutation: {
        async addUsuario(obj, {input}) {
            const usuario = new Usuario({...input, correoValidado: false});
            await usuario.save();
            return usuario;
        },
        async updUsuario(obj, {id, input}) {
            const usuario = await Usuario.findByIdAndUpdate(id);
            return usuario;
        },
        async delUsuario(obj, {id}) {
            await Usuario.deleteOne({_id: id});
            return {
                message: "Usuario eliminado"
            };
        },
        
        async addAdmin(obj, {input}) {
            const admin = new Admin(input);
            await admin.save();
            return admin;
        },
        async addCajero(obj, {input}) {
            const cajero = new Cajero(input);
            await cajero.save();
            return cajero;
        }
    }
};

let apolloServer = null;
const corsOption ={
    origin: 'http://localhost:8020', // Para que el cliente pueda acceder al servidor. Cambiar puerto si es necesario.
    credentials: false
};
async function startServer() {
    apolloServer = new ApolloServer({typeDefs, resolvers, corsOption});
    await apolloServer.start();
    apolloServer.applyMiddleware({app, cors: false});
};

startServer();

const app = express();
app.use(cors());
app.listen(8020, function(){
    console.log("Graphql Iniciado");
})