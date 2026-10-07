/* PHASE 3 - staging tables.
   Staging holds the cleaned and validated rows of the files processed in the
   current ETL run. It is truncated at the start of every run; the warehouse
   procedures then MERGE it into the star schema.                            */

IF OBJECT_ID('stg.Faculties') IS NULL
CREATE TABLE stg.Faculties (
    FacultyID INT NOT NULL, FacultyName NVARCHAR(100) NOT NULL,
    Dean NVARCHAR(150) NULL, EstablishedYear INT NULL);

IF OBJECT_ID('stg.Departments') IS NULL
CREATE TABLE stg.Departments (
    DepartmentID INT NOT NULL, DepartmentName NVARCHAR(150) NOT NULL, FacultyID INT NOT NULL);

IF OBJECT_ID('stg.Teachers') IS NULL
CREATE TABLE stg.Teachers (
    TeacherID INT NOT NULL, TeacherName NVARCHAR(150) NOT NULL, DepartmentID INT NOT NULL,
    ExperienceYears INT NULL, AcademicDegree NVARCHAR(50) NULL, EmploymentType NVARCHAR(50) NULL);

IF OBJECT_ID('stg.Courses') IS NULL
CREATE TABLE stg.Courses (
    CourseID INT NOT NULL, CourseName NVARCHAR(150) NOT NULL, DepartmentID INT NOT NULL,
    Credits INT NOT NULL, Semester INT NOT NULL, CourseType NVARCHAR(30) NULL);

IF OBJECT_ID('stg.Students') IS NULL
CREATE TABLE stg.Students (
    StudentID INT NOT NULL, FirstName NVARCHAR(60) NOT NULL, LastName NVARCHAR(60) NOT NULL,
    GroupName NVARCHAR(20) NOT NULL, Gender NVARCHAR(20) NOT NULL, DateOfBirth DATE NULL, FacultyID INT NOT NULL,
    DepartmentID INT NOT NULL, EnrollmentYear INT NOT NULL, StudyYear INT NOT NULL,
    ScholarshipStatus NVARCHAR(30) NULL, TuitionStatus NVARCHAR(30) NULL,
    Status NVARCHAR(30) NOT NULL, StatusDate DATE NULL);

IF OBJECT_ID('stg.Enrollments') IS NULL
CREATE TABLE stg.Enrollments (
    EnrollmentID INT NOT NULL, StudentID INT NOT NULL, CourseID INT NOT NULL,
    TeacherID INT NOT NULL, Semester NVARCHAR(20) NOT NULL, AcademicYear CHAR(9) NOT NULL);

IF OBJECT_ID('stg.Grades') IS NULL
CREATE TABLE stg.Grades (
    GradeID INT NOT NULL, StudentID INT NOT NULL, CourseID INT NOT NULL,
    CurrentScore DECIMAL(5,1) NOT NULL,      -- joriy nazorat
    MidtermScore DECIMAL(5,1) NOT NULL,      -- oraliq nazorat
    FinalScore DECIMAL(5,1) NOT NULL,        -- yakuniy nazorat
    AttendanceScore DECIMAL(5,1) NOT NULL,   -- attendance in the course, %
    ExamAdmitted NVARCHAR(5) NOT NULL,       -- Ha / Yo'q: admitted to the final control
    FinalGrade NVARCHAR(2) NOT NULL, GPA DECIMAL(3,1) NOT NULL, IsMidtermImputed BIT NOT NULL);

IF OBJECT_ID('stg.Attendance') IS NULL
CREATE TABLE stg.Attendance (
    AttendanceID BIGINT NOT NULL, StudentID INT NOT NULL, CourseID INT NOT NULL,
    [Date] DATE NOT NULL, Status NVARCHAR(20) NOT NULL);

IF OBJECT_ID('stg.Payments') IS NULL
CREATE TABLE stg.Payments (
    PaymentID INT NOT NULL, StudentID INT NOT NULL, TuitionAmount DECIMAL(14,2) NOT NULL,
    PaidAmount DECIMAL(14,2) NOT NULL, RemainingDebt DECIMAL(14,2) NOT NULL,
    PaymentDate DATE NOT NULL, PaymentStatus NVARCHAR(30) NOT NULL);

IF OBJECT_ID('stg.Assignments') IS NULL
CREATE TABLE stg.Assignments (
    AssignmentID BIGINT NOT NULL, StudentID INT NOT NULL, CourseID INT NOT NULL,
    SubmissionDate DATE NULL, Score DECIMAL(5,1) NOT NULL,
    SubmissionStatus NVARCHAR(30) NOT NULL, DueDate DATE NOT NULL);

IF OBJECT_ID('stg.AcademicWarnings') IS NULL
CREATE TABLE stg.AcademicWarnings (
    WarningID INT NOT NULL, StudentID INT NOT NULL, WarningType NVARCHAR(50) NOT NULL,
    WarningDate DATE NOT NULL, Severity NVARCHAR(20) NOT NULL);
GO
