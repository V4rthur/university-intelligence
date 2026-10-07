/* PHASE 5 - star schema: dimension tables.
   Dimensions describe WHO / WHAT / WHEN; facts (02_facts.sql) hold the events
   and measures. Dimension keys are the stable source IDs, which keeps every
   load idempotent (re-running the ETL updates rows instead of duplicating).  */

IF OBJECT_ID('dw.DimFaculty') IS NULL
CREATE TABLE dw.DimFaculty (
    FacultyKey      INT NOT NULL CONSTRAINT PK_DimFaculty PRIMARY KEY,
    FacultyName     NVARCHAR(100) NOT NULL,
    Dean            NVARCHAR(150) NULL,
    EstablishedYear INT NULL
);

IF OBJECT_ID('dw.DimDepartment') IS NULL
CREATE TABLE dw.DimDepartment (
    DepartmentKey  INT NOT NULL CONSTRAINT PK_DimDepartment PRIMARY KEY,
    DepartmentName NVARCHAR(150) NOT NULL,
    FacultyKey     INT NOT NULL CONSTRAINT FK_DimDepartment_Faculty REFERENCES dw.DimFaculty
);

IF OBJECT_ID('dw.DimTeacher') IS NULL
CREATE TABLE dw.DimTeacher (
    TeacherKey      INT NOT NULL CONSTRAINT PK_DimTeacher PRIMARY KEY,
    TeacherName     NVARCHAR(150) NOT NULL,
    DepartmentKey   INT NOT NULL CONSTRAINT FK_DimTeacher_Department REFERENCES dw.DimDepartment,
    ExperienceYears INT NULL,
    AcademicDegree  NVARCHAR(50) NULL,
    EmploymentType  NVARCHAR(50) NULL
);

IF OBJECT_ID('dw.DimCourse') IS NULL
CREATE TABLE dw.DimCourse (
    CourseKey          INT NOT NULL CONSTRAINT PK_DimCourse PRIMARY KEY,
    CourseName         NVARCHAR(150) NOT NULL,
    DepartmentKey      INT NOT NULL CONSTRAINT FK_DimCourse_Department REFERENCES dw.DimDepartment,
    Credits            INT NOT NULL,
    CurriculumSemester INT NOT NULL,       -- 1..8, position in the study plan
    CourseType         NVARCHAR(30) NULL
);

IF OBJECT_ID('dw.DimStudent') IS NULL
CREATE TABLE dw.DimStudent (
    StudentKey        INT NOT NULL CONSTRAINT PK_DimStudent PRIMARY KEY,
    FirstName         NVARCHAR(60) NOT NULL,
    LastName          NVARCHAR(60) NOT NULL,
    FullName          AS (LastName + N' ' + FirstName) PERSISTED,
    GroupName         NVARCHAR(20) NOT NULL,   -- academic group, e.g. IQ-22-03
    Gender            NVARCHAR(20) NOT NULL,
    DateOfBirth       DATE NULL,
    FacultyKey        INT NOT NULL CONSTRAINT FK_DimStudent_Faculty REFERENCES dw.DimFaculty,
    DepartmentKey     INT NOT NULL CONSTRAINT FK_DimStudent_Department REFERENCES dw.DimDepartment,
    EnrollmentYear    INT NOT NULL,
    StudyYear         INT NOT NULL,
    ScholarshipStatus NVARCHAR(30) NULL,
    TuitionStatus     NVARCHAR(30) NULL,
    Status            NVARCHAR(30) NOT NULL,   -- Faol / Chetlashtirilgan / Bitirgan
    StatusDate        DATE NULL
);

-- one row per academic semester; SemesterKey grows by 1 every semester
IF OBJECT_ID('dw.DimSemester') IS NULL
BEGIN
    CREATE TABLE dw.DimSemester (
        SemesterKey   INT NOT NULL CONSTRAINT PK_DimSemester PRIMARY KEY,
        AcademicYear  CHAR(9) NOT NULL,
        SemesterName  NVARCHAR(20) NOT NULL,     -- Kuz / Bahor
        SemesterLabel NVARCHAR(40) NOT NULL,
        StartDate     DATE NOT NULL,             -- contiguous ranges: every date
        EndDate       DATE NOT NULL              -- belongs to exactly one semester
    );
    WITH y AS (SELECT TOP (11) 2021 + ROW_NUMBER() OVER (ORDER BY (SELECT 1)) AS Y
               FROM sys.all_objects)
    INSERT dw.DimSemester
    SELECT (Y - 2022) * 2, CONCAT(Y, '-', Y + 1), N'Kuz', CONCAT(Y, '-', Y + 1, N' Kuz'),
           DATEFROMPARTS(Y, 9, 1), DATEFROMPARTS(Y + 1, 1, 31) FROM y
    UNION ALL
    SELECT (Y - 2022) * 2 + 1, CONCAT(Y, '-', Y + 1), N'Bahor', CONCAT(Y, '-', Y + 1, N' Bahor'),
           DATEFROMPARTS(Y + 1, 2, 1), DATEFROMPARTS(Y + 1, 8, 31) FROM y;
END;

IF OBJECT_ID('dw.DimDate') IS NULL
BEGIN
    CREATE TABLE dw.DimDate (
        DateKey      INT NOT NULL CONSTRAINT PK_DimDate PRIMARY KEY,   -- yyyymmdd
        [Date]       DATE NOT NULL UNIQUE,
        [Year]       INT NOT NULL,
        [Quarter]    INT NOT NULL,
        [Month]      INT NOT NULL,
        MonthName    NVARCHAR(20) NOT NULL,
        [Day]        INT NOT NULL,
        WeekdayName  NVARCHAR(20) NOT NULL,
        IsWeekend    BIT NOT NULL,
        SemesterKey  INT NULL CONSTRAINT FK_DimDate_Semester REFERENCES dw.DimSemester
    );
    WITH n AS (SELECT TOP (DATEDIFF(DAY, '2022-01-01', '2033-08-31') + 1)
                      ROW_NUMBER() OVER (ORDER BY (SELECT 1)) - 1 AS i
               FROM sys.all_objects a CROSS JOIN sys.all_objects b),
         d AS (SELECT DATEADD(DAY, i, CAST('2022-01-01' AS DATE)) AS dt FROM n)
    INSERT dw.DimDate
    SELECT CONVERT(INT, FORMAT(dt, 'yyyyMMdd')), dt, YEAR(dt), DATEPART(QUARTER, dt), MONTH(dt),
           CHOOSE(MONTH(dt), N'Yanvar', N'Fevral', N'Mart', N'Aprel', N'May', N'Iyun', N'Iyul',
                  N'Avgust', N'Sentabr', N'Oktabr', N'Noyabr', N'Dekabr'),
           DAY(dt),
           -- (days since Monday 1900-01-01) % 7 is independent of SET DATEFIRST
           CHOOSE(DATEDIFF(DAY, '1900-01-01', dt) % 7 + 1, N'Dushanba', N'Seshanba',
                  N'Chorshanba', N'Payshanba', N'Juma', N'Shanba', N'Yakshanba'),
           IIF(DATEDIFF(DAY, '1900-01-01', dt) % 7 >= 5, 1, 0),
           s.SemesterKey
    FROM d LEFT JOIN dw.DimSemester s ON d.dt BETWEEN s.StartDate AND s.EndDate;
END;
GO
