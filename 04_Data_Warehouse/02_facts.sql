/* PHASE 5 - star schema: fact tables.
   Each fact row is one event (an enrollment, a grade, an attendance check,
   a tuition invoice, an assignment, a warning) with foreign keys to the
   dimensions. The primary key is the source ID, so re-loading is idempotent. */

IF OBJECT_ID('dw.FactEnrollments') IS NULL
CREATE TABLE dw.FactEnrollments (
    EnrollmentID INT NOT NULL CONSTRAINT PK_FactEnrollments PRIMARY KEY,
    StudentKey   INT NOT NULL CONSTRAINT FK_FactEnr_Student  REFERENCES dw.DimStudent,
    CourseKey    INT NOT NULL CONSTRAINT FK_FactEnr_Course   REFERENCES dw.DimCourse,
    TeacherKey   INT NOT NULL CONSTRAINT FK_FactEnr_Teacher  REFERENCES dw.DimTeacher,
    SemesterKey  INT NOT NULL CONSTRAINT FK_FactEnr_Semester REFERENCES dw.DimSemester,
    INDEX IX_FactEnr_StudentCourse UNIQUE (StudentKey, CourseKey),
    INDEX IX_FactEnr_Semester (SemesterKey, TeacherKey)
);

IF OBJECT_ID('dw.FactGrades') IS NULL
CREATE TABLE dw.FactGrades (
    GradeID          INT NOT NULL CONSTRAINT PK_FactGrades PRIMARY KEY,
    StudentKey       INT NOT NULL CONSTRAINT FK_FactGrd_Student  REFERENCES dw.DimStudent,
    CourseKey        INT NOT NULL CONSTRAINT FK_FactGrd_Course   REFERENCES dw.DimCourse,
    TeacherKey       INT NOT NULL CONSTRAINT FK_FactGrd_Teacher  REFERENCES dw.DimTeacher,
    SemesterKey      INT NOT NULL CONSTRAINT FK_FactGrd_Semester REFERENCES dw.DimSemester,
    CurrentScore     DECIMAL(5,1) NOT NULL,     -- joriy nazorat (max 20)
    MidtermScore     DECIMAL(5,1) NOT NULL,     -- oraliq nazorat (max 30)
    FinalScore       DECIMAL(5,1) NOT NULL,     -- yakuniy nazorat (max 50)
    AttendanceScore  DECIMAL(5,1) NOT NULL,     -- attendance in the course, %
    TotalScore       DECIMAL(5,1) NOT NULL,     -- derived: current + midterm + final (max 100)
    IsAdmitted       BIT NOT NULL,              -- admitted to the final control
    FinalGrade       NVARCHAR(2) NOT NULL,      -- 5 / 4 / 3 / 2
    GradePoints      DECIMAL(3,1) NOT NULL,
    Credits          INT NOT NULL,
    IsFailed         BIT NOT NULL,
    IsMidtermImputed BIT NOT NULL,
    INDEX IX_FactGrd_StudentSemester (StudentKey, SemesterKey),
    INDEX IX_FactGrd_CourseSemester (CourseKey, SemesterKey)
);

IF OBJECT_ID('dw.FactAttendance') IS NULL
CREATE TABLE dw.FactAttendance (
    AttendanceID BIGINT NOT NULL CONSTRAINT PK_FactAttendance PRIMARY KEY,
    StudentKey   INT NOT NULL CONSTRAINT FK_FactAtt_Student  REFERENCES dw.DimStudent,
    CourseKey    INT NOT NULL CONSTRAINT FK_FactAtt_Course   REFERENCES dw.DimCourse,
    DateKey      INT NOT NULL CONSTRAINT FK_FactAtt_Date     REFERENCES dw.DimDate,
    SemesterKey  INT NOT NULL CONSTRAINT FK_FactAtt_Semester REFERENCES dw.DimSemester,
    Status       NVARCHAR(20) NOT NULL,          -- Keldi / Kelmadi / Sababli
    IsPresent    BIT NOT NULL,
    INDEX IX_FactAtt_StudentSemester (StudentKey, SemesterKey) INCLUDE (IsPresent, CourseKey)
);

IF OBJECT_ID('dw.FactPayments') IS NULL
CREATE TABLE dw.FactPayments (
    PaymentID     INT NOT NULL CONSTRAINT PK_FactPayments PRIMARY KEY,
    StudentKey    INT NOT NULL CONSTRAINT FK_FactPay_Student  REFERENCES dw.DimStudent,
    DateKey       INT NOT NULL CONSTRAINT FK_FactPay_Date     REFERENCES dw.DimDate,
    SemesterKey   INT NOT NULL CONSTRAINT FK_FactPay_Semester REFERENCES dw.DimSemester,
    TuitionAmount DECIMAL(14,2) NOT NULL,
    PaidAmount    DECIMAL(14,2) NOT NULL,
    RemainingDebt DECIMAL(14,2) NOT NULL,
    PaymentStatus NVARCHAR(30) NOT NULL,
    INDEX IX_FactPay_StudentSemester (StudentKey, SemesterKey)
);

IF OBJECT_ID('dw.FactAssignments') IS NULL
CREATE TABLE dw.FactAssignments (
    AssignmentID      BIGINT NOT NULL CONSTRAINT PK_FactAssignments PRIMARY KEY,
    StudentKey        INT NOT NULL CONSTRAINT FK_FactAsg_Student  REFERENCES dw.DimStudent,
    CourseKey         INT NOT NULL CONSTRAINT FK_FactAsg_Course   REFERENCES dw.DimCourse,
    SemesterKey       INT NOT NULL CONSTRAINT FK_FactAsg_Semester REFERENCES dw.DimSemester,
    DueDateKey        INT NOT NULL CONSTRAINT FK_FactAsg_DueDate  REFERENCES dw.DimDate,
    SubmissionDateKey INT NULL     CONSTRAINT FK_FactAsg_SubDate  REFERENCES dw.DimDate,
    Score             DECIMAL(5,1) NOT NULL,
    SubmissionStatus  NVARCHAR(30) NOT NULL,
    IsSubmitted       BIT NOT NULL,
    IsLate            BIT NOT NULL,
    INDEX IX_FactAsg_StudentSemester (StudentKey, SemesterKey) INCLUDE (IsSubmitted, IsLate, Score)
);

IF OBJECT_ID('dw.FactWarnings') IS NULL
CREATE TABLE dw.FactWarnings (
    WarningID   INT NOT NULL CONSTRAINT PK_FactWarnings PRIMARY KEY,
    StudentKey  INT NOT NULL CONSTRAINT FK_FactWrn_Student  REFERENCES dw.DimStudent,
    DateKey     INT NOT NULL CONSTRAINT FK_FactWrn_Date     REFERENCES dw.DimDate,
    SemesterKey INT NOT NULL CONSTRAINT FK_FactWrn_Semester REFERENCES dw.DimSemester,
    WarningType NVARCHAR(50) NOT NULL,
    Severity    NVARCHAR(20) NOT NULL,
    INDEX IX_FactWrn_StudentSemester (StudentKey, SemesterKey)
);

/* Analytical snapshot: one row per student per semester. It is rebuilt from the
   facts at the end of every ETL run and is the single source for the
   dashboard KPIs, the ML features and the AI agent tools.                    */
IF OBJECT_ID('dw.FactStudentSemester') IS NULL
CREATE TABLE dw.FactStudentSemester (
    StudentKey         INT NOT NULL CONSTRAINT FK_FactSS_Student  REFERENCES dw.DimStudent,
    SemesterKey        INT NOT NULL CONSTRAINT FK_FactSS_Semester REFERENCES dw.DimSemester,
    FacultyKey         INT NOT NULL,
    DepartmentKey      INT NOT NULL,
    StudySemester      INT NOT NULL,            -- 1..8 for this student
    CourseLoad         INT NOT NULL,
    Credits            INT NOT NULL,
    SemGPA             DECIMAL(4,2) NOT NULL,
    CumGPA             DECIMAL(4,2) NOT NULL,
    PrevGPA            DECIMAL(4,2) NULL,       -- NULL in the first semester
    AttendanceRate     DECIMAL(5,4) NULL,
    FailedCourses      INT NOT NULL,
    CumFailedCourses   INT NOT NULL,
    AvgAssignmentScore DECIMAL(5,1) NULL,
    SubmissionRate     DECIMAL(5,4) NULL,
    WarningsCum        INT NOT NULL,            -- warnings issued BEFORE this semester ended
    DebtRatio          DECIMAL(5,4) NOT NULL,   -- remaining debt / tuition (0 for grant)
    AvgTeacherLoad     DECIMAL(8,1) NULL,       -- students taught by this student's teachers
    IsAtRisk           BIT NOT NULL,            -- risk definition applied to THIS semester
    IsLastSemester     BIT NOT NULL,            -- student's most recent semester in the data
    CONSTRAINT PK_FactStudentSemester PRIMARY KEY (StudentKey, SemesterKey),
    INDEX IX_FactSS_Semester (SemesterKey, FacultyKey)
);
GO
