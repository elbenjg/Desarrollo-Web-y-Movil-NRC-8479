const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors'); // Revisa si como cliente tengo certificado de seguridad. Y al revés el servidor.

const {ApolloServer, gql} = require('apollo-server-express'); 
const Usuario = require('./models/usuario');

mongoose.connect('mongodb://localhost:27017/semana5db'); // Para conectarse a la base de datos de MongoDB.
const typeDefs = gql`
    type Usuario {
        id: ID!
        nombre: String!
        pass: String!
    }
    input UsuarioInput {
        nombre: String!
        pass: String!
    }
    type Alert{ # Para que avise si se borró algo. 
        message: String!
    }
    type Query {   # Para consultas
        getUsuarios: [Usuario]
        getUsuarioById(id: ID!): Usuario
    }
    type Mutation { # Para crear, actualizar y borrar.
        addUsuario(input: UsuarioInput): Usuario
        updUsuario(id: ID!, input: UsuarioInput): Usuario
        delUsuario(id: ID!): Alert
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
            if (usuarioBus == NULL) {
                return NULL; 
            } else{
                return usuarioBus;
            }
        }
    },
    Mutation: {
        async addUsuario(obj, {input}) {
            const usuario = new Usuario(input);
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