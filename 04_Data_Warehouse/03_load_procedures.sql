/* PHASE 5 - warehouse load procedures (staging -> star schema).
   Every load is a MERGE on the primary key: new rows are inserted, changed
   rows are updated, unchanged rows are left alone. Running the ETL twice on
   the same files therefore never creates duplicates.
   Each MERGE is audited in etl.LoadAudit (staged / inserted / updated /
   orphaned), which the pipeline uses for its own tests.                     */

CREATE OR ALTER PROCEDURE dw.usp_LoadDimensions @RunID INT
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    CREATE TABLE #a (act NVARCHAR(10));

    MERGE dw.DimFaculty t USING stg.Faculties s ON t.FacultyKey = s.FacultyID
    WHEN MATCHED AND EXISTS (SELECT s.FacultyName, s.Dean, s.EstablishedYear
                             EXCEPT SELECT t.FacultyName, t.Dean, t.EstablishedYear)
        THEN UPDATE SET FacultyName = s.FacultyName, Dean = s.Dean,
                        EstablishedYear = s.EstablishedYear
    WHEN NOT MATCHED THEN INSERT (FacultyKey, FacultyName, Dean, EstablishedYear)
        VALUES (s.FacultyID, s.FacultyName, s.Dean, s.EstablishedYear)
    OUTPUT $action INTO #a;
    INSERT etl.LoadAudit SELECT @RunID, N'DimFaculty', (SELECT COUNT(*) FROM stg.Faculties),
        COUNT(CASE WHEN act = 'INSERT' THEN 1 END), COUNT(CASE WHEN act = 'UPDATE' THEN 1 END), 0 FROM #a;
    TRUNCATE TABLE #a;

    MERGE dw.DimDepartment t USING stg.Departments s ON t.DepartmentKey = s.DepartmentID
    WHEN MATCHED AND EXISTS (SELECT s.DepartmentName, s.FacultyID
                             EXCEPT SELECT t.DepartmentName, t.FacultyKey)
        THEN UPDATE SET DepartmentName = s.DepartmentName, FacultyKey = s.FacultyID
    WHEN NOT MATCHED THEN INSERT (DepartmentKey, DepartmentName, FacultyKey)
        VALUES (s.DepartmentID, s.DepartmentName, s.FacultyID)
    OUTPUT $action INTO #a;
    INSERT etl.LoadAudit SELECT @RunID, N'DimDepartment', (SELECT COUNT(*) FROM stg.Departments),
        COUNT(CASE WHEN act = 'INSERT' THEN 1 END), COUNT(CASE WHEN act = 'UPDATE' THEN 1 END), 0 FROM #a;
    TRUNCATE TABLE #a;

    MERGE dw.DimTeacher t USING stg.Teachers s ON t.TeacherKey = s.TeacherID
    WHEN MATCHED AND EXISTS (
            SELECT s.TeacherName, s.DepartmentID, s.ExperienceYears, s.AcademicDegree, s.EmploymentType
            EXCEPT SELECT t.TeacherName, t.DepartmentKey, t.ExperienceYears, t.AcademicDegree, t.EmploymentType)
        THEN UPDATE SET TeacherName = s.TeacherName, DepartmentKey = s.DepartmentID,
                        ExperienceYears = s.ExperienceYears, AcademicDegree = s.AcademicDegree,
                        EmploymentType = s.EmploymentType
    WHEN NOT MATCHED THEN INSERT (TeacherKey, TeacherName, DepartmentKey, ExperienceYears,
                                  AcademicDegree, EmploymentType)
        VALUES (s.TeacherID, s.TeacherName, s.DepartmentID, s.ExperienceYears,
                s.AcademicDegree, s.EmploymentType)
    OUTPUT $action INTO #a;
    INSERT etl.LoadAudit SELECT @RunID, N'DimTeacher', (SELECT COUNT(*) FROM stg.Teachers),
        COUNT(CASE WHEN act = 'INSERT' THEN 1 END), COUNT(CASE WHEN act = 'UPDATE' THEN 1 END), 0 FROM #a;
    TRUNCATE TABLE #a;

    MERGE dw.DimCourse t USING stg.Courses s ON t.CourseKey = s.CourseID
    WHEN MATCHED AND EXISTS (
            SELECT s.CourseName, s.DepartmentID, s.Credits, s.Semester, s.CourseType
            EXCEPT SELECT t.CourseName, t.DepartmentKey, t.Credits, t.CurriculumSemester, t.CourseType)
        THEN UPDATE SET CourseName = s.CourseName, DepartmentKey = s.DepartmentID,
                        Credits = s.Credits, CurriculumSemester = s.Semester,
                        CourseType = s.CourseType
    WHEN NOT MATCHED THEN INSERT (CourseKey, CourseName, DepartmentKey, Credits,
                                  CurriculumSemester, CourseType)
        VALUES (s.CourseID, s.CourseName, s.DepartmentID, s.Credits, s.Semester, s.CourseType)
    OUTPUT $action INTO #a;
    INSERT etl.LoadAudit SELECT @RunID, N'DimCourse', (SELECT COUNT(*) FROM stg.Courses),
        COUNT(CASE WHEN act = 'INSERT' THEN 1 END), COUNT(CASE WHEN act = 'UPDATE' THEN 1 END), 0 FROM #a;
    TRUNCATE TABLE #a;

    -- students change over time (study year, status): type-1 update in place
    MERGE dw.DimStudent t USING stg.Students s ON t.StudentKey = s.StudentID
    WHEN MATCHED AND EXISTS (
            SELECT s.FirstName, s.LastName, s.GroupName, s.Gender, s.DateOfBirth, s.FacultyID, s.DepartmentID,
                   s.EnrollmentYear, s.StudyYear, s.ScholarshipStatus, s.TuitionStatus, s.Status, s.StatusDate
            EXCEPT
            SELECT t.FirstName, t.LastName, t.GroupName, t.Gender, t.DateOfBirth, t.FacultyKey, t.DepartmentKey,
                   t.EnrollmentYear, t.StudyYear, t.ScholarshipStatus, t.TuitionStatus, t.Status, t.StatusDate)
        THEN UPDATE SET FirstName = s.FirstName, LastName = s.LastName, GroupName = s.GroupName,
                        Gender = s.Gender, DateOfBirth = s.DateOfBirth, FacultyKey = s.FacultyID,
                        DepartmentKey = s.DepartmentID, EnrollmentYear = s.EnrollmentYear,
                        StudyYear = s.StudyYear, ScholarshipStatus = s.ScholarshipStatus,
                        TuitionStatus = s.TuitionStatus, Status = s.Status, StatusDate = s.StatusDate
    WHEN NOT MATCHED THEN INSERT (StudentKey, FirstName, LastName, GroupName, Gender, DateOfBirth,
                                  FacultyKey, DepartmentKey, EnrollmentYear, StudyYear,
                                  ScholarshipStatus, TuitionStatus, Status, StatusDate)
        VALUES (s.StudentID, s.FirstName, s.LastName, s.GroupName, s.Gender, s.DateOfBirth,
                s.FacultyID, s.DepartmentID, s.EnrollmentYear, s.StudyYear, s.ScholarshipStatus,
                s.TuitionStatus, s.Status, s.StatusDate)
    OUTPUT $action INTO #a;
    INSERT etl.LoadAudit SELECT @RunID, N'DimStudent', (SELECT COUNT(*) FROM stg.Students),
        COUNT(CASE WHEN act = 'INSERT' THEN 1 END), COUNT(CASE WHEN act = 'UPDATE' THEN 1 END), 0 FROM #a;
END;
GO

CREATE OR ALTER PROCEDURE dw.usp_LoadFacts @RunID INT
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    CREATE TABLE #a (act NVARCHAR(10));
    DECLARE @staged BIGINT, @joined BIGINT;

    ---------------------------------------------------------------- enrollments
    SELECT e.EnrollmentID, e.StudentID, e.CourseID, e.TeacherID, s.SemesterKey
    INTO #enr
    FROM stg.Enrollments e
    JOIN dw.DimSemester s ON s.AcademicYear = e.AcademicYear AND s.SemesterName = e.Semester;
    SELECT @staged = COUNT(*) FROM stg.Enrollments; SELECT @joined = COUNT(*) FROM #enr;

    MERGE dw.FactEnrollments t USING #enr s ON t.EnrollmentID = s.EnrollmentID
    WHEN MATCHED AND EXISTS (SELECT s.StudentID, s.CourseID, s.TeacherID, s.SemesterKey
                             EXCEPT SELECT t.StudentKey, t.CourseKey, t.TeacherKey, t.SemesterKey)
        THEN UPDATE SET StudentKey = s.StudentID, CourseKey = s.CourseID,
                        TeacherKey = s.TeacherID, SemesterKey = s.SemesterKey
    WHEN NOT MATCHED THEN INSERT (EnrollmentID, StudentKey, CourseKey, TeacherKey, SemesterKey)
        VALUES (s.EnrollmentID, s.StudentID, s.CourseID, s.TeacherID, s.SemesterKey)
    OUTPUT $action INTO #a;
    INSERT etl.LoadAudit SELECT @RunID, N'FactEnrollments', @staged,
        COUNT(CASE WHEN act = 'INSERT' THEN 1 END), COUNT(CASE WHEN act = 'UPDATE' THEN 1 END),
        @staged - @joined FROM #a;
    TRUNCATE TABLE #a;

    --------------------------------------------------------------------- grades
    -- the semester and the teacher of a grade come from the matching enrollment
    SELECT g.GradeID, g.StudentID, g.CourseID, fe.TeacherKey, fe.SemesterKey,
           g.CurrentScore, g.MidtermScore, g.FinalScore, g.AttendanceScore,
           -- 100-point system: joriy + oraliq + yakuniy nazorat. The grade is
           -- derived from the total here (not copied from the source), so it
           -- always agrees with the scores: 90+ = 5, 70+ = 4, 60+ = 3, else 2.
           CAST(x.Total AS DECIMAL(5,1)) AS TotalScore,
           CAST(IIF(g.ExamAdmitted = N'Ha', 1, 0) AS BIT) AS IsAdmitted,
           CAST(CASE WHEN x.Total >= 90 THEN N'5' WHEN x.Total >= 70 THEN N'4'
                     WHEN x.Total >= 60 THEN N'3' ELSE N'2' END AS NVARCHAR(2)) AS FinalGrade,
           CAST(CASE WHEN x.Total >= 90 THEN 5 WHEN x.Total >= 70 THEN 4
                     WHEN x.Total >= 60 THEN 3 ELSE 2 END AS DECIMAL(3,1)) AS GPA,
           c.Credits,
           CAST(IIF(x.Total < 60, 1, 0) AS BIT) AS IsFailed, g.IsMidtermImputed
    INTO #grd
    FROM stg.Grades g
    CROSS APPLY (SELECT g.CurrentScore + g.MidtermScore + g.FinalScore AS Total) x
    JOIN dw.FactEnrollments fe ON fe.StudentKey = g.StudentID AND fe.CourseKey = g.CourseID
    JOIN dw.DimCourse c ON c.CourseKey = g.CourseID;
    SELECT @staged = COUNT(*) FROM stg.Grades; SELECT @joined = COUNT(*) FROM #grd;

    MERGE dw.FactGrades t USING #grd s ON t.GradeID = s.GradeID
    WHEN MATCHED AND EXISTS (
            SELECT s.StudentID, s.CourseID, s.TeacherKey, s.SemesterKey, s.CurrentScore, s.MidtermScore,
                   s.FinalScore, s.AttendanceScore, s.IsAdmitted, s.FinalGrade, s.GPA, s.Credits,
                   s.IsMidtermImputed
            EXCEPT
            SELECT t.StudentKey, t.CourseKey, t.TeacherKey, t.SemesterKey, t.CurrentScore, t.MidtermScore,
                   t.FinalScore, t.AttendanceScore, t.IsAdmitted, t.FinalGrade, t.GradePoints, t.Credits,
                   t.IsMidtermImputed)
        THEN UPDATE SET StudentKey = s.StudentID, CourseKey = s.CourseID, TeacherKey = s.TeacherKey,
                        SemesterKey = s.SemesterKey, CurrentScore = s.CurrentScore,
                        MidtermScore = s.MidtermScore, FinalScore = s.FinalScore,
                        AttendanceScore = s.AttendanceScore, TotalScore = s.TotalScore,
                        IsAdmitted = s.IsAdmitted, FinalGrade = s.FinalGrade, GradePoints = s.GPA,
                        Credits = s.Credits, IsFailed = s.IsFailed,
                        IsMidtermImputed = s.IsMidtermImputed
    WHEN NOT MATCHED THEN INSERT (GradeID, StudentKey, CourseKey, TeacherKey, SemesterKey,
                                  CurrentScore, MidtermScore, FinalScore, AttendanceScore,
                                  TotalScore, IsAdmitted, FinalGrade, GradePoints, Credits, IsFailed,
                                  IsMidtermImputed)
        VALUES (s.GradeID, s.StudentID, s.CourseID, s.TeacherKey, s.SemesterKey, s.CurrentScore,
                s.MidtermScore, s.FinalScore, s.AttendanceScore, s.TotalScore, s.IsAdmitted,
                s.FinalGrade, s.GPA, s.Credits, s.IsFailed, s.IsMidtermImputed)
    OUTPUT $action INTO #a;
    INSERT etl.LoadAudit SELECT @RunID, N'FactGrades', @staged,
        COUNT(CASE WHEN act = 'INSERT' THEN 1 END), COUNT(CASE WHEN act = 'UPDATE' THEN 1 END),
        @staged - @joined FROM #a;
    TRUNCATE TABLE #a;

    ----------------------------------------------------------------- attendance
    SELECT a.AttendanceID, a.StudentID, a.CourseID, d.DateKey, d.SemesterKey, a.Status,
           CAST(IIF(a.Status = N'Keldi', 1, 0) AS BIT) AS IsPresent
    INTO #att
    FROM stg.Attendance a
    JOIN dw.DimDate d ON d.[Date] = a.[Date] AND d.SemesterKey IS NOT NULL;
    SELECT @staged = COUNT(*) FROM stg.Attendance; SELECT @joined = COUNT(*) FROM #att;

    MERGE dw.FactAttendance t USING #att s ON t.AttendanceID = s.AttendanceID
    WHEN MATCHED AND EXISTS (SELECT s.StudentID, s.CourseID, s.DateKey, s.Status
                             EXCEPT SELECT t.StudentKey, t.CourseKey, t.DateKey, t.Status)
        THEN UPDATE SET StudentKey = s.StudentID, CourseKey = s.CourseID, DateKey = s.DateKey,
                        SemesterKey = s.SemesterKey, Status = s.Status, IsPresent = s.IsPresent
    WHEN NOT MATCHED THEN INSERT (AttendanceID, StudentKey, CourseKey, DateKey, SemesterKey,
                                  Status, IsPresent)
        VALUES (s.AttendanceID, s.StudentID, s.CourseID, s.DateKey, s.SemesterKey, s.Status, s.IsPresent)
    OUTPUT $action INTO #a;
    INSERT etl.LoadAudit SELECT @RunID, N'FactAttendance', @staged,
        COUNT(CASE WHEN act = 'INSERT' THEN 1 END), COUNT(CASE WHEN act = 'UPDATE' THEN 1 END),
        @staged - @joined FROM #a;
    TRUNCATE TABLE #a;

    ------------------------------------------------------------------- payments
    SELECT p.PaymentID, p.StudentID, d.DateKey, d.SemesterKey, p.TuitionAmount, p.PaidAmount,
           p.RemainingDebt, p.PaymentStatus
    INTO #pay
    FROM stg.Payments p
    JOIN dw.DimDate d ON d.[Date] = p.PaymentDate AND d.SemesterKey IS NOT NULL;
    SELECT @staged = COUNT(*) FROM stg.Payments; SELECT @joined = COUNT(*) FROM #pay;

    MERGE dw.FactPayments t USING #pay s ON t.PaymentID = s.PaymentID
    WHEN MATCHED AND EXISTS (
            SELECT s.StudentID, s.DateKey, s.TuitionAmount, s.PaidAmount, s.RemainingDebt, s.PaymentStatus
            EXCEPT
            SELECT t.StudentKey, t.DateKey, t.TuitionAmount, t.PaidAmount, t.RemainingDebt, t.PaymentStatus)
        THEN UPDATE SET StudentKey = s.StudentID, DateKey = s.DateKey, SemesterKey = s.SemesterKey,
                        TuitionAmount = s.TuitionAmount, PaidAmount = s.PaidAmount,
                        RemainingDebt = s.RemainingDebt, PaymentStatus = s.PaymentStatus
    WHEN NOT MATCHED THEN INSERT (PaymentID, StudentKey, DateKey, SemesterKey, TuitionAmount,
                                  PaidAmount, RemainingDebt, PaymentStatus)
        VALUES (s.PaymentID, s.StudentID, s.DateKey, s.SemesterKey, s.TuitionAmount, s.PaidAmount,
                s.RemainingDebt, s.PaymentStatus)
    OUTPUT $action INTO #a;
    INSERT etl.LoadAudit SELECT @RunID, N'FactPayments', @staged,
        COUNT(CASE WHEN act = 'INSERT' THEN 1 END), COUNT(CASE WHEN act = 'UPDATE' THEN 1 END),
        @staged - @joined FROM #a;
    TRUNCATE TABLE #a;

    ---------------------------------------------------------------- assignments
    SELECT a.AssignmentID, a.StudentID, a.CourseID, fe.SemesterKey, dd.DateKey AS DueDateKey,
           sd.DateKey AS SubmissionDateKey, a.Score, a.SubmissionStatus,
           CAST(IIF(a.SubmissionStatus = N'Topshirilmadi', 0, 1) AS BIT) AS IsSubmitted,
           CAST(IIF(a.SubmissionStatus = N'Kechikib topshirildi', 1, 0) AS BIT) AS IsLate
    INTO #asg
    FROM stg.Assignments a
    JOIN dw.FactEnrollments fe ON fe.StudentKey = a.StudentID AND fe.CourseKey = a.CourseID
    JOIN dw.DimDate dd ON dd.[Date] = a.DueDate
    LEFT JOIN dw.DimDate sd ON sd.[Date] = a.SubmissionDate;
    SELECT @staged = COUNT(*) FROM stg.Assignments; SELECT @joined = COUNT(*) FROM #asg;

    MERGE dw.FactAssignments t USING #asg s ON t.AssignmentID = s.AssignmentID
    WHEN MATCHED AND EXISTS (
            SELECT s.StudentID, s.CourseID, s.SemesterKey, s.DueDateKey, s.SubmissionDateKey,
                   s.Score, s.SubmissionStatus
            EXCEPT
            SELECT t.StudentKey, t.CourseKey, t.SemesterKey, t.DueDateKey, t.SubmissionDateKey,
                   t.Score, t.SubmissionStatus)
        THEN UPDATE SET StudentKey = s.StudentID, CourseKey = s.CourseID, SemesterKey = s.SemesterKey,
                        DueDateKey = s.DueDateKey, SubmissionDateKey = s.SubmissionDateKey,
                        Score = s.Score, SubmissionStatus = s.SubmissionStatus,
                        IsSubmitted = s.IsSubmitted, IsLate = s.IsLate
    WHEN NOT MATCHED THEN INSERT (AssignmentID, StudentKey, CourseKey, SemesterKey, DueDateKey,
                                  SubmissionDateKey, Score, SubmissionStatus, IsSubmitted, IsLate)
        VALUES (s.AssignmentID, s.StudentID, s.CourseID, s.SemesterKey, s.DueDateKey,
                s.SubmissionDateKey, s.Score, s.SubmissionStatus, s.IsSubmitted, s.IsLate)
    OUTPUT $action INTO #a;
    INSERT etl.LoadAudit SELECT @RunID, N'FactAssignments', @staged,
        COUNT(CASE WHEN act = 'INSERT' THEN 1 END), COUNT(CASE WHEN act = 'UPDATE' THEN 1 END),
        @staged - @joined FROM #a;
    TRUNCATE TABLE #a;

    ------------------------------------------------------------------- warnings
    SELECT w.WarningID, w.StudentID, d.DateKey, d.SemesterKey, w.WarningType, w.Severity
    INTO #wrn
    FROM stg.AcademicWarnings w
    JOIN dw.DimDate d ON d.[Date] = w.WarningDate AND d.SemesterKey IS NOT NULL;
    SELECT @staged = COUNT(*) FROM stg.AcademicWarnings; SELECT @joined = COUNT(*) FROM #wrn;

    MERGE dw.FactWarnings t USING #wrn s ON t.WarningID = s.WarningID
    WHEN MATCHED AND EXISTS (SELECT s.StudentID, s.DateKey, s.WarningType, s.Severity
                             EXCEPT SELECT t.StudentKey, t.DateKey, t.WarningType, t.Severity)
        THEN UPDATE SET StudentKey = s.StudentID, DateKey = s.DateKey, SemesterKey = s.SemesterKey,
                        WarningType = s.WarningType, Severity = s.Severity
    WHEN NOT MATCHED THEN INSERT (WarningID, StudentKey, DateKey, SemesterKey, WarningType, Severity)
        VALUES (s.WarningID, s.StudentID, s.DateKey, s.SemesterKey, s.WarningType, s.Severity)
    OUTPUT $action INTO #a;
    INSERT etl.LoadAudit SELECT @RunID, N'FactWarnings', @staged,
        COUNT(CASE WHEN act = 'INSERT' THEN 1 END), COUNT(CASE WHEN act = 'UPDATE' THEN 1 END),
        @staged - @joined FROM #a;
END;
GO

/* Rebuild the student-semester snapshot from the facts (full refresh inside a
   transaction, so readers never see an empty table).                        */
CREATE OR ALTER PROCEDURE dw.usp_BuildStudentSemester
    @AtRiskGPA DECIMAL(4,2) = 2.0,
    @AtRiskFailed INT = 2
AS
BEGIN
    SET NOCOUNT ON; SET XACT_ABORT ON;
    BEGIN TRANSACTION;
    TRUNCATE TABLE dw.FactStudentSemester;

    WITH g AS (
        SELECT StudentKey, SemesterKey, COUNT(*) AS CourseLoad, SUM(Credits) AS Credits,
               SUM(GradePoints * Credits) AS QualityPoints,
               SUM(CAST(IsFailed AS INT)) AS Failed
        FROM dw.FactGrades GROUP BY StudentKey, SemesterKey),
    a AS (
        SELECT StudentKey, SemesterKey, AVG(CAST(IsPresent AS FLOAT)) AS AttendanceRate
        FROM dw.FactAttendance GROUP BY StudentKey, SemesterKey),
    asg AS (
        SELECT StudentKey, SemesterKey, AVG(Score) AS AvgScore,
               AVG(CAST(IsSubmitted AS FLOAT)) AS SubmissionRate
        FROM dw.FactAssignments GROUP BY StudentKey, SemesterKey),
    p AS (
        SELECT StudentKey, SemesterKey,
               SUM(RemainingDebt) / NULLIF(SUM(TuitionAmount), 0) AS DebtRatio
        FROM dw.FactPayments GROUP BY StudentKey, SemesterKey),
    w AS (
        SELECT StudentKey, SemesterKey, COUNT(*) AS Warnings
        FROM dw.FactWarnings GROUP BY StudentKey, SemesterKey),
    tload AS (
        SELECT TeacherKey, SemesterKey, COUNT(*) AS Students
        FROM dw.FactEnrollments GROUP BY TeacherKey, SemesterKey),
    tl AS (
        SELECT e.StudentKey, e.SemesterKey, AVG(CAST(t.Students AS FLOAT)) AS AvgTeacherLoad
        FROM dw.FactEnrollments e
        JOIN tload t ON t.TeacherKey = e.TeacherKey AND t.SemesterKey = e.SemesterKey
        GROUP BY e.StudentKey, e.SemesterKey)
    INSERT dw.FactStudentSemester
    SELECT g.StudentKey, g.SemesterKey, st.FacultyKey, st.DepartmentKey,
           g.SemesterKey - 2 * (st.EnrollmentYear - 2022) + 1,
           g.CourseLoad, g.Credits,
           g.QualityPoints / g.Credits,
           SUM(g.QualityPoints) OVER (PARTITION BY g.StudentKey ORDER BY g.SemesterKey
                                      ROWS UNBOUNDED PRECEDING)
             / SUM(g.Credits) OVER (PARTITION BY g.StudentKey ORDER BY g.SemesterKey
                                    ROWS UNBOUNDED PRECEDING),
           LAG(g.QualityPoints / g.Credits) OVER (PARTITION BY g.StudentKey ORDER BY g.SemesterKey),
           a.AttendanceRate, g.Failed,
           SUM(g.Failed) OVER (PARTITION BY g.StudentKey ORDER BY g.SemesterKey
                               ROWS UNBOUNDED PRECEDING),
           asg.AvgScore, asg.SubmissionRate,
           SUM(ISNULL(w.Warnings, 0)) OVER (PARTITION BY g.StudentKey ORDER BY g.SemesterKey
                                            ROWS UNBOUNDED PRECEDING),
           ISNULL(p.DebtRatio, 0), tl.AvgTeacherLoad,
           IIF(g.QualityPoints / g.Credits < @AtRiskGPA OR g.Failed >= @AtRiskFailed, 1, 0),
           IIF(g.SemesterKey = MAX(g.SemesterKey) OVER (PARTITION BY g.StudentKey), 1, 0)
    FROM g
    JOIN dw.DimStudent st ON st.StudentKey = g.StudentKey
    LEFT JOIN a   ON a.StudentKey = g.StudentKey   AND a.SemesterKey = g.SemesterKey
    LEFT JOIN asg ON asg.StudentKey = g.StudentKey AND asg.SemesterKey = g.SemesterKey
    LEFT JOIN p   ON p.StudentKey = g.StudentKey   AND p.SemesterKey = g.SemesterKey
    LEFT JOIN w   ON w.StudentKey = g.StudentKey   AND w.SemesterKey = g.SemesterKey
    LEFT JOIN tl  ON tl.StudentKey = g.StudentKey  AND tl.SemesterKey = g.SemesterKey;

    COMMIT;
END;
GO
