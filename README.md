# Cloud Resume Processing & Recruitment Platform

A cloud-based resume processing and recruitment platform that helps recruiters manage job postings and rank candidates based on how well their resumes match the required skills of a job.

## Overview

Recruiters can create and manage job postings by specifying the skills required for each role. Candidates can browse available postings and submit their resumes as PDF files.

After a resume is uploaded, the application:

1. Stores the submission metadata in Cloud SQL.
2. Stores the PDF resume in Cloud Storage.
3. Publishes a `resume-uploaded` event through Google Cloud Pub/Sub.
4. Delivers the event to an independent Cloud Run worker.
5. Extracts the resume text and matches it against the required skills.
6. Calculates a compatibility score.
7. Stores the result in Cloud SQL.
8. Makes the ranked submissions available to the recruiter.

## Features

### Recruiter

- User registration and login
- Create job postings
- View job postings
- Update job postings
- Delete job postings
- View submitted candidates
- View candidates ranked by compatibility score and identified by email

### Candidate

- User registration and login
- Browse available job postings
- View job details
- Upload resume PDFs
- Track submission processing status
- View compatibility score and matched skills

## Architecture

The system uses three independent Cloud Run services:

- **React Frontend** — web interface for recruiters and candidates
- **FastAPI Backend** — REST API and application logic
- **Resume Processing Worker** — asynchronous resume extraction and scoring

Supporting Google Cloud services:

- **Cloud SQL (PostgreSQL)** — structured application data
- **Cloud Storage** — uploaded resume PDFs
- **Cloud Pub/Sub** — asynchronous communication between API and worker
- **IAM / Service Accounts** — service-to-service access control
- **Cloud Logging** — application and worker logs

### Processing Flow

```text
Candidate / Recruiter
        |
        v
React Frontend
   Cloud Run
        |
        | REST / HTTPS
        v
FastAPI Backend
   Cloud Run
     |    |    \
     |    |     \--> Pub/Sub --> Cloud Run Worker
     |    |                              |   |
     |    |                              |   +--> Cloud Storage
     |    |                              +------> Cloud SQL
     |    |
     |    +--------> Cloud Storage
     +-------------> Cloud SQL
```

The API returns `202 Accepted` after accepting a resume submission, while extraction and scoring continue asynchronously through Pub/Sub and the processing worker.

## Technology Stack

**Frontend**

- React
- TypeScript
- Vite

**Backend**

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT authentication
- Argon2 password hashing

**Cloud**

- Google Cloud Run
- Google Cloud SQL
- Google Cloud Storage
- Google Cloud Pub/Sub
- Google Cloud IAM
- Google Cloud Logging

## REST API

The backend exposes RESTful APIs for authentication, job posting CRUD, resume submissions, submission status, and recruiter ranking.

### Main Endpoints

```text
POST   /auth/signup
POST   /auth/login

POST   /postings
GET    /postings
GET    /postings/{id}
PUT    /postings/{id}
DELETE /postings/{id}

POST   /postings/{id}/submissions
GET    /submissions/{id}
GET    /postings/{id}/submissions?sort=score
```

## Scoring

The compatibility score is calculated using required skill matching:

```text
Compatibility Score =
(Matched Required Skills / Total Required Skills) x 100
```

The worker also stores the matched skills so recruiters can understand the basis of the compatibility score.

## Database

The application uses PostgreSQL on Cloud SQL with three primary entities:

- `users`
- `job_postings`
- `submissions`

The `submissions` entity connects candidates to job postings and stores processing status, compatibility score, matched skills, and the Cloud Storage path of the uploaded resume.

## Deployment

The application is deployed in the `asia-south1` Google Cloud region.

## Cloud Computing Concepts Demonstrated

The project demonstrates:

- Serverless computing
- Cloud-based database management
- Cloud object storage
- Event-driven architecture
- Asynchronous processing
- Independent service scaling
- IAM and service accounts
- Managed cloud infrastructure

## Project Structure

```text
resume-ip/
├── backend/
│   ├── app/
│   ├── alembic/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
└── README.md
```

## Project Status

Deployed and operational on Google Cloud.

The complete workflow has been tested through:

```text
Job Creation
    |
    v
Resume Upload
    |
    v
Cloud Storage
    |
    v
Pub/Sub Event
    |
    v
Cloud Run Worker
    |
    v
Resume Processing
    |
    v
Compatibility Score
    |
    v
Recruiter Ranking
```
