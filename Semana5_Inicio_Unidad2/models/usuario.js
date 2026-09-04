const mongoose = require('mongoose');

const usuarioSchema = new mongoose.Schema({
    nombre: String,
    pass: String,
    rut: String,
    direccion: String,
    comuna: String,
    provincia: String,
    region: String,
    fnac: String,
    sexo: String,
    telefono: String,
    correo: String,
    correoValidado: { type: Boolean, default: false },
    rol: {type: String, enum: ['usuario', 'admin', 'cajero'], default: 'usuario'}
});

module.exports = mongoose.model('Usuario', usuarioSchema); 
