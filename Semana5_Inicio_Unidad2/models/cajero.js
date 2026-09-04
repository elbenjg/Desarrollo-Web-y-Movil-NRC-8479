const mongoose = require('mongoose');

const cajeroSchema = new mongoose.Schema({
    nombre: String,
    pass: String,
    rol: {type: String, enum: ['usuario', 'admin', 'cajero'], default: 'cajero'}
});

module.exports = mongoose.model('Cajero', cajeroSchema);



