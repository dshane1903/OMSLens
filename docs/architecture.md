# OMSCS Course Intelligence Architecture

## Goal

Answer course-planning questions for OMSCS students using real student data, starting with OMSCentral reviews and growing into a multi-source retrieval platform.

## Current Shape

- **API Gateway** is the public entrypoint.
- **Ingestion Service** discovers OMSCentral courses, scrapes review pages, normalizes review documents, and stores snapshots plus source-backed records in Postgres.
- **Postgres + pgvector** stores course metadata, source documents, and later chunk embeddings.
- **Embedding Service** is ready for the next ingestion stage.
- **Retrieval Service** is ready to query embedded chunks.
- **LLM Service** is ready to turn retrieved context into grounded answers.

## OMSCentral Flow

1. Client calls `POST /sources/omscentral/scrape` on the API gateway.
2. API gateway forwards the request to the ingestion service.
3. Ingestion service fetches the OMSCentral homepage and extracts the course catalog from the server-rendered payload.
4. Ingestion service fetches each selected `/courses/{slug}/reviews` page.
5. Course metadata and review bodies are normalized into source-backed documents.
6. Course rows are upserted into `course_catalog`.
7. Review rows are upserted into `documents`.
8. JSON snapshots are stored on disk for debugging and downstream processing.

## Data Model

- `course_catalog` stores one row per external course source record.
- `documents` stores one row per review or future source document.
- `chunks` remains the downstream table for retrieval-ready text embeddings.

## Immediate Tradeoffs

- Review ingestion is synchronous today.
- Embedding is intentionally deferred so the first milestone stays focused on collecting clean source data.
- OMSCentral parsing depends on the current Next.js payload and page structure, so parser tests are important as the site evolves.

## Near-Term Evolution

- move source ingestion onto RabbitMQ
- add a processing worker for chunking and validation
- embed review chunks and wire them into retrieval
- add citation metadata through to final answers
- expand ingestion to Reddit, syllabi, and grade distributions
