# DA3 Step 4 API Smoke Test

Overall: **PASS**

| step | expected | actual |
| --- | --- | --- |
| Register synthetic recruiter | HTTP 201 | HTTP 201 |
| Register synthetic candidate | HTTP 201 | HTTP 201 |
| Log in synthetic recruiter | HTTP 200 and access token | HTTP 200 |
| Validate recruiter login token | non-empty access token | access token received and retained only in memory |
| Log in synthetic candidate | HTTP 200 and access token | HTTP 200 |
| Validate candidate login token | non-empty access token | access token received and retained only in memory |
| Recruiter creates posting | HTTP 201 and posting id | HTTP 201 |
| Validate created posting | non-empty posting id | posting id received |
| Recruiter reads posting | HTTP 200 with matching id | HTTP 200 |
| Validate recruiter read response | response id matches created posting | id matched |
| Candidate reads posting | HTTP 200 with matching id | HTTP 200 |
| Validate candidate read response | response id matches created posting | id matched |
| Candidate create posting is rejected | HTTP 403 | HTTP 403 |
| Candidate update posting is rejected | HTTP 403 | HTTP 403 |
| Candidate delete posting is rejected | HTTP 403 | HTTP 403 |
| Recruiter updates posting | HTTP 200 with updated title | HTTP 200 |
| Validate recruiter update response | response title matches update | title matched |
| Recruiter deletes posting | HTTP 204 | HTTP 204 |
| Deleted posting is not found | HTTP 404 | HTTP 404 |
