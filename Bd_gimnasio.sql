CREATE DATABASE IF NOT EXISTS pruebaAPI;
USE fastapi;


CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(50) UNIQUE NOT NULL
);

-- Inserción de los roles iniciales
INSERT IGNORE INTO roles (id, nombre) VALUES 
(1, 'Administrador'),
(2, 'Cliente');

CREATE TABLE IF NOT EXISTS usuarios (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    correo VARCHAR(150) UNIQUE NOT NULL,
    rol_id INT NOT NULL DEFAULT 2,
    password VARCHAR(255) NOT NULL
);

-- 2. Tabla de Planes (Alineada con planesModel)
CREATE TABLE IF NOT EXISTS planes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tipo VARCHAR(100) NOT NULL,
    precio DECIMAL(10, 2) NOT NULL,
    duracion INT NOT NULL,
    estado VARCHAR(500) DEFAULT 'activo'
);

-- 3. Tabla de Membresías (Alineada con membresiasModel)
CREATE TABLE IF NOT EXISTS membresias_usuario (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    plan_id INT NOT NULL,
    fecha_inicio DATETIME NOT NULL,
    fecha_fin DATETIME NOT NULL,
    estado VARCHAR(50) DEFAULT 'activa',
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (plan_id) REFERENCES planes(id) ON DELETE CASCADE
);

drop table if exists membresias_usuario;
drop table if exists usuarios;
ALTER TABLE usuarios ADD COLUMN activo TINYINT(1) NOT NULL DEFAULT 1;
