/* Staff records of what was done for a student at risk (dashboard, risk page).

   app - data people type into the system, as opposed to dw (loaded from files)
         and ml (written by the model). It is the only data here that cannot be
         regenerated, so `--rebuild` saves and restores it (see etl_pipeline.py).

   No foreign key to dw.DimStudent: the warehouse is reloaded by the pipeline and
   must never fail or lose staff notes because of them. Idempotent.            */

IF SCHEMA_ID('app') IS NULL EXEC('CREATE SCHEMA app');
GO

IF OBJECT_ID('app.Intervention') IS NULL
CREATE TABLE app.Intervention (
    InterventionID INT IDENTITY(1,1) PRIMARY KEY,
    StudentKey     INT            NOT NULL,
    SemesterKey    INT            NOT NULL,          -- semester the record was opened in
    Type           NVARCHAR(60)   NOT NULL,          -- what was done: talk, tutoring, ...
    Status         NVARCHAR(30)   NOT NULL,          -- Rejalashtirilgan / Jarayonda / Yakunlangan
    Outcome        NVARCHAR(30)   NULL,              -- filled in when it is finished
    Note           NVARCHAR(1000) NULL,
    CreatedBy      NVARCHAR(100)  NOT NULL,
    CreatedAt      DATETIME2(0)   NOT NULL DEFAULT SYSDATETIME(),
    UpdatedBy      NVARCHAR(100)  NULL,
    UpdatedAt      DATETIME2(0)   NULL
);
GO

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_Intervention_Student')
    CREATE INDEX IX_Intervention_Student ON app.Intervention (StudentKey, CreatedAt DESC);
GO
