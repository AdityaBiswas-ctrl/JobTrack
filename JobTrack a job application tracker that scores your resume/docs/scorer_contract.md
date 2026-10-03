# ATS Resume Scorer API contract

Verified from the local scorer source at `C:\Users\KIIT\ats_resume_scorer`,
specifically `app/main.py`, `app/scorer.py`, and `app/utils.py`, and confirmed
against the running service's `/openapi.json`.

## Scoring endpoint

- Method and path: `POST /score`
- Content type: `multipart/form-data`
- Required file field: `resume_file` (the scorer checks the filename ends in
  `.pdf`, then extracts text from the uploaded PDF bytes)
- Required form field: `job_description` (non-empty text)
- Authentication: none is declared by the route.
- Health check: `GET /health`.

## Success response

The route returns HTTP 200 and a JSON object containing:

| Field | Type | Meaning |
|---|---|---|
| `status` | string | `"success"` |
| `filename` | string | Uploaded PDF filename |
| `similarity_score` | number | Semantic similarity from 0 to 100 |
| `rating` | string | Human-readable match category |
| `matched_keywords` | array of strings | Extracted keywords present in both texts |
| `missing_keywords` | array of strings | Job-description keywords absent from resume |
| `resume_keyword_count` | integer | Number of extracted resume keywords |
| `jd_keyword_count` | integer | Number of extracted job-description keywords |

JobTrack uses `similarity_score` as its `match_score` and stores
`missing_keywords`. The other returned fields are validated by the client, but
are not currently persisted in JobTrack's score row.

## Error responses

- HTTP 400: filename does not end in `.pdf`, or job description is empty.
- HTTP 422: PDF text extraction fails or no extractable resume text exists.
- Other unhandled errors may be returned by the scorer runtime.

## Latency

The source does not define an SLA or typical response time. The scoring path
extracts PDF text, runs sentence-transformer embeddings and spaCy keyword
extraction. One verified local JobTrack-to-scorer call with a synthetic PDF
completed in 613 ms; this is a single observed request, not a latency
guarantee or a cold-start measurement. JobTrack's outbound timeout is
configured by `SCORER_TIMEOUT_SECONDS`.
