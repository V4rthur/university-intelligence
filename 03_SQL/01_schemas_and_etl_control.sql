/* PHASE 3 - schemas and ETL control tables.
   The database itself is created by 02_ETL/etl_pipeline.py (CREATE DATABASE
   cannot run inside the database it creates). Every statement is idempotent.

   stg  - staging: cleaned, typed rows of the files processed in the current run
   dw   - data warehouse: star schema (see 04_Data_Warehouse)
   etl  - pipeline control: run log, file log, data-quality log, rejected rows
   ml   - model outputs written back by 06_ML                                  */

IF SCHEMA_ID('stg') IS NULL EXEC('CREATE SCHEMA stg');
IF SCHEMA_ID('dw')  IS NULL EXEC('CREATE SCHEMA dw');
IF SCHEMA_ID('etl') IS NULL EXEC('CREATE SCHEMA etl');
IF SCHEMA_ID('ml')  IS NULL EXEC('CREATE SCHEMA ml');
GO

IF OBJECT_ID('etl.RunLog') IS NULL
CREATE TABLE etl.RunLog (
    RunID          INT IDENTITY(1,1) PRIMARY KEY,
    StartedAt      DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    FinishedAt     DATETIME2(0) NULL,
    Status         NVARCHAR(20) NOT NULL DEFAULT N'RUNNING',   -- RUNNING / SUCCESS / FAILED
    FilesProcessed INT NULL,
    RowsRead       BIGINT NULL,
    RowsLoaded     BIGINT NULL,
    RowsRejected   BIGINT NULL,
    Message        NVARCHAR(2000) NULL
);

-- one row per source file: a file is re-processed only when its hash changes
IF OBJECT_ID('etl.FileLog') IS NULL
CREATE TABLE etl.FileLog (
    FileName     NVARCHAR(260) NOT NULL PRIMARY KEY,
    TableName    NVARCHAR(60)  NOT NULL,
    FileHash     CHAR(32)      NOT NULL,
    RowsRead     BIGINT NOT NULL,
    RowsLoaded   BIGINT NOT NULL,
    RowsRejected BIGINT NOT NULL,
    RunID        INT NOT NULL,
    ProcessedAt  DATETIME2(0) NOT NULL DEFAULT SYSDATETIME()
);

-- one row per (file, check): replaced when the file is re-processed, so the
-- table always describes the current state of every source file
IF OBJECT_ID('etl.DataQualityLog') IS NULL
CREATE TABLE etl.DataQualityLog (
    FileName   NVARCHAR(260) NOT NULL,
    TableName  NVARCHAR(60)  NOT NULL,
    CheckName  NVARCHAR(60)  NOT NULL,   -- missing / duplicate / invalid / orphan / ...
    Action     NVARCHAR(20)  NOT NULL,   -- FIXED / REJECTED / FLAGGED
    IssueCount BIGINT NOT NULL,
    RunID      INT NOT NULL,
    CONSTRAINT PK_DataQualityLog PRIMARY KEY (FileName, CheckName)
);

IF OBJECT_ID('etl.RejectedRecords') IS NULL
CREATE TABLE etl.RejectedRecords (
    RejectID  BIGINT IDENTITY(1,1) PRIMARY KEY,
    RunID     INT NOT NULL,
    FileName  NVARCHAR(260) NOT NULL,
    TableName NVARCHAR(60) NOT NULL,
    Reason    NVARCHAR(60) NOT NULL,
    RawRecord NVARCHAR(MAX) NOT NULL
);

-- what the warehouse load did with the staged rows of each run
IF OBJECT_ID('etl.LoadAudit') IS NULL
CREATE TABLE etl.LoadAudit (
    RunID        INT NOT NULL,
    TableName    NVARCHAR(60) NOT NULL,
    RowsStaged   BIGINT NOT NULL,
    RowsInserted BIGINT NOT NULL,
    RowsUpdated  BIGINT NOT NULL,
    RowsOrphaned BIGINT NOT NULL,
    CONSTRAINT PK_LoadAudit PRIMARY KEY (RunID, TableName)
);
GO
