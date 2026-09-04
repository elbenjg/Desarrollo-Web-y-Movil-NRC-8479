const mongoose = require('mongoose');

const adminSchema = new mongoose.Schema({
    nombre: String,
    pass: String,
    rol: {type: String, enum: ['usuario', 'admin', 'cajero'], default: 'admin'}
});

module.exports = mongoose.model('Admin', adminSchema); 