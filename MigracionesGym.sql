-- =====================================================================
-- 02_migracion_existente.sql  ->  para una base de datos que YA TIENES.
-- Se puede ejecutar varias veces sin romper nada (revisa si cada cosa ya existe).
-- No borra datos. Haz un respaldo antes de ejecutarlo:
--     mysqldump -u root -p fastAPI > respaldo_antes_de_migrar.sql
-- =====================================================================
USE fastAPI;   -- debe coincidir con DB_NAME de tu .env

-- ---------------------------------------------------------------------
-- 1) usuarios.activo  (borrado lógico)
--    Las cuentas que ya existen quedan activas (DEFAULT 1).
-- ---------------------------------------------------------------------
SET @existe := (SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'usuarios' AND COLUMN_NAME = 'activo');
SET @sql := IF(@existe = 0,
    'ALTER TABLE usuarios ADD COLUMN activo TINYINT(1) NOT NULL DEFAULT 1',
    'SELECT ''usuarios.activo ya existe: sin cambios'' AS aviso');
PREPARE paso FROM @sql; EXECUTE paso; DEALLOCATE PREPARE paso;

-- ---------------------------------------------------------------------
-- 2) usuarios.correo_verificado
--    Truco: la columna se crea con DEFAULT 1, así las cuentas que YA existen
--    quedan verificadas (si no, nadie podría volver a iniciar sesión).
--    Justo después el DEFAULT pasa a 0, para que las cuentas NUEVAS nazcan
--    sin verificar. Si ejecutas el script otra vez, no vuelve a tocar los datos.
-- ---------------------------------------------------------------------
SET @existe := (SELECT COUNT(*) FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'usuarios' AND COLUMN_NAME = 'correo_verificado');
SET @sql := IF(@existe = 0,
    'ALTER TABLE usuarios ADD COLUMN correo_verificado TINYINT(1) NOT NULL DEFAULT 1',
    'SELECT ''usuarios.correo_verificado ya existe: sin cambios'' AS aviso');
PREPARE paso FROM @sql; EXECUTE paso; DEALLOCATE PREPARE paso;

ALTER TABLE usuarios ALTER COLUMN correo_verificado SET DEFAULT 0;

-- ---------------------------------------------------------------------
-- 3) Tabla de códigos de verificación / recuperación
--    (si usas Base.metadata.create_all(), SQLAlchemy también la crea sola)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS codigos_verificacion (
    id INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id INT NOT NULL,
    proposito VARCHAR(30) NOT NULL,
    codigo_hash VARCHAR(64) NOT NULL,
    expira_en DATETIME NOT NULL,
    intentos INT NOT NULL DEFAULT 0,
    usado TINYINT(1) NOT NULL DEFAULT 0,
    creado_en DATETIME NOT NULL,
    INDEX ix_codigos_verificacion_usuario_id (usuario_id),
    CONSTRAINT fk_codigos_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------------------------------------------------------------
-- 4) Comprobación: debes ver las columnas activo y correo_verificado
-- ---------------------------------------------------------------------
SHOW COLUMNS FROM usuarios;