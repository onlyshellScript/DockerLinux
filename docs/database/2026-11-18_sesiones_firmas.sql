-- SIGOS · 18/11/2026 · Sesiones revocables y firma del tecnico en evidencias (SQL Server).
-- Equivale a la migracion Alembic a7c8e9f0b1d2 (services/api/migrations/versions/). Usar este script mientras
-- `flask db upgrade` siga fallando por la cadena de migraciones duplicada (ver esquema-espanol-y-orm.md §4).
-- Ejecutar con sqlcmd o SSMS (usa separadores GO). Solo agrega tablas y columnas NULL: no modifica ni borra datos existentes. Es idempotente.
-- Tras aplicarlo:  UPDATE alembic_version SET version_num = 'a7c8e9f0b1d2' WHERE version_num = '615483f3bc21';
SET XACT_ABORT ON;
BEGIN TRANSACTION;

IF OBJECT_ID(N'dbo.SesionesUsuario', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.SesionesUsuario (
        IdSesion          NVARCHAR(36)      NOT NULL CONSTRAINT PK_SesionesUsuario PRIMARY KEY,
        IdUsuario         INT               NOT NULL CONSTRAINT FK_SesionesUsuario_Usuarios REFERENCES dbo.Usuarios (IdUsuario),
        CreadaEn          DATETIMEOFFSET    NOT NULL,
        ExpiraEn          DATETIMEOFFSET    NOT NULL,
        RevocadaEn        DATETIMEOFFSET    NULL,
        MotivoRevocacion  NVARCHAR(40)      NULL,
        IpOrigen          NVARCHAR(45)      NULL
    );
    CREATE INDEX IX_SesionesUsuario_IdUsuario ON dbo.SesionesUsuario (IdUsuario);
END;

IF OBJECT_ID(N'dbo.FirmasTecnico', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.FirmasTecnico (
        IdFirmaTecnico       INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_FirmasTecnico PRIMARY KEY,
        IdUsuario            INT               NOT NULL CONSTRAINT FK_FirmasTecnico_Usuarios REFERENCES dbo.Usuarios (IdUsuario),
        ClaveAlmacenamiento  NVARCHAR(120)     NOT NULL CONSTRAINT UQ_FirmasTecnico_ClaveAlmacenamiento UNIQUE,
        TipoArchivo          NVARCHAR(100)     NOT NULL,
        TamanoArchivo        INT               NOT NULL,
        Sha256               NVARCHAR(64)      NOT NULL,
        Version              INT               NOT NULL CONSTRAINT DF_FirmasTecnico_Version DEFAULT (1),
        EsActiva             BIT               NOT NULL CONSTRAINT DF_FirmasTecnico_EsActiva DEFAULT (1),
        CreadaEn             DATETIMEOFFSET    NOT NULL,
        ReemplazadaEn        DATETIMEOFFSET    NULL
    );
    CREATE INDEX IX_FirmasTecnico_IdUsuario ON dbo.FirmasTecnico (IdUsuario);
END;

IF COL_LENGTH(N'dbo.Evidencias', N'IdFirmaTecnico') IS NULL
BEGIN
    ALTER TABLE dbo.Evidencias ADD IdFirmaTecnico INT NULL;
END;
IF COL_LENGTH(N'dbo.Evidencias', N'FirmaTecnicoSha256') IS NULL
    ALTER TABLE dbo.Evidencias ADD FirmaTecnicoSha256 NVARCHAR(64) NULL;
IF COL_LENGTH(N'dbo.Evidencias', N'IdTecnicoFirmante') IS NULL
    ALTER TABLE dbo.Evidencias ADD IdTecnicoFirmante INT NULL;
IF COL_LENGTH(N'dbo.Evidencias', N'FechaFirmaTecnico') IS NULL
    ALTER TABLE dbo.Evidencias ADD FechaFirmaTecnico DATETIMEOFFSET NULL;
COMMIT TRANSACTION;
GO

-- Las FK e indices sobre columnas recien agregadas van en otro lote (SQL Server compila el lote completo).
BEGIN TRANSACTION;
IF OBJECT_ID(N'dbo.FK_Evidencias_FirmasTecnico', N'F') IS NULL
    ALTER TABLE dbo.Evidencias ADD CONSTRAINT FK_Evidencias_FirmasTecnico
        FOREIGN KEY (IdFirmaTecnico) REFERENCES dbo.FirmasTecnico (IdFirmaTecnico);
IF OBJECT_ID(N'dbo.FK_Evidencias_TecnicoFirmante', N'F') IS NULL
    ALTER TABLE dbo.Evidencias ADD CONSTRAINT FK_Evidencias_TecnicoFirmante
        FOREIGN KEY (IdTecnicoFirmante) REFERENCES dbo.Usuarios (IdUsuario);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = N'IX_Evidencias_IdFirmaTecnico' AND object_id = OBJECT_ID(N'dbo.Evidencias'))
    CREATE INDEX IX_Evidencias_IdFirmaTecnico ON dbo.Evidencias (IdFirmaTecnico);
COMMIT TRANSACTION;
GO
