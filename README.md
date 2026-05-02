# OMSCS Course Intelligence Platform

This repo is the start of a course intelligence product for OMSCS students.

The first shipped slice is an `OMSCentral` ingestion path:

- discover the full OMSCentral catalog from the homepage payload
- scrape individual course review pages
- normalize course metadata and review text
- persist source-backed review documents in Postgres
- save per-course JSON snapshots for downstream processing

The existing retrieval, embedding, and LLM services are still here so we can grow this into the full cited Q&A experience next.

## Current Services

- `api-gateway` proxies public requests into the platform
- `ingestion-service` scrapes OMSCentral and stores normalized source documents
- `embedding-service` exposes embeddings for the later pipeline stages
- `retrieval-service` exposes vector retrieval over stored chunks
- `llm-service` produces grounded answers from retrieved context

## Local Run

```bash
docker compose -f infra/docker-compose.yml up --build
```

Then trigger the first scrape through the gateway:

```bash
curl -X POST http://localhost:8000/sources/omscentral/scrape \
  -H "Content-Type: application/json" \
  -d '{"course_slugs":["software-architecture-and-design"],"persist":true}'
```

You can also run the scraper directly from the ingestion service:

```bash
PYTHONPATH=services/ingestion-service:. python3 services/ingestion-service/app/scrape_omscentral.py \
  --course-slug software-architecture-and-design \
  --persist
```

Snapshots are written under `DOCUMENT_STORAGE_PATH/omscentral/`.

## Next Build Targets

- add a processing worker that turns raw review documents into chunks
- publish chunk jobs onto RabbitMQ instead of doing work inline
- embed persisted review chunks into pgvector
- add Reddit, syllabi, and grade distribution ingestion
- return cited answers for semester planning questions
