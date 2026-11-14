# Modules

Each folder is one part of the report's architecture. Keep the layers apart,
so the code is easy to read and to port to PHP later:

```
<module>/
  domain.py   # plain Python rules, no FastAPI or SQL (e.g. NPS formula)
  repo.py     # SQL, always through liana_survey_shared.db.tenant_connection()
  routes.py   # FastAPI router: HTTP in and out only
```

| Module | Report component | Requirements |
|---|---|---|
| surveys | Survey Manager | R02, R06, R07 |
| analytics | Data Analyzer | R03 |
| respondent | Respondent Survey Service | R01 |

Empty for now. Each backlog card fills in one piece.
