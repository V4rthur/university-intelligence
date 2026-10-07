/* Read-only identity for the AI agent's free-SQL tool (07_AI_Agent/agent_tools.py).

   The tool already rejects anything that is not a single SELECT, but a text
   filter can be wrong. So the query itself runs as this database user, which
   has no login and holds nothing but SELECT on the tables the agent may read:
   whatever slips through the filter, SQL Server refuses to write.

   Not granted on purpose: stg (work tables), etl.RejectedRecords (raw rejected
   rows) and app (staff notes about students). Every statement is idempotent. */

IF DATABASE_PRINCIPAL_ID('uis_agent_reader') IS NULL
    CREATE USER uis_agent_reader WITHOUT LOGIN;
GO

GRANT SELECT ON SCHEMA::dw TO uis_agent_reader;
GRANT SELECT ON SCHEMA::ml TO uis_agent_reader;
GRANT SELECT ON OBJECT::etl.RunLog         TO uis_agent_reader;
GRANT SELECT ON OBJECT::etl.FileLog        TO uis_agent_reader;
GRANT SELECT ON OBJECT::etl.DataQualityLog TO uis_agent_reader;
GRANT SELECT ON OBJECT::etl.LoadAudit      TO uis_agent_reader;
GO
