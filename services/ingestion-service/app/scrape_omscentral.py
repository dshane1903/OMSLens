import argparse
import asyncio
import json

from app.main import settings, upsert_course, upsert_reviews, write_snapshot
from app.scrapers.omscentral import OMSCentralClient


async def run() -> None:
    parser = argparse.ArgumentParser(description="Scrape OMSCentral course reviews.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--course-slug", action="append", default=[])
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

    client = OMSCentralClient(settings)
    try:
        catalog = await client.fetch_catalog()
        catalog_by_slug = {course.slug: course for course in catalog}

        if args.course_slug:
            selected = [catalog_by_slug[slug] for slug in args.course_slug]
        else:
            selected = catalog

        if args.limit is not None:
            selected = selected[: args.limit]

        results: list[dict[str, object]] = []
        for course in selected:
            hydrated_course, reviews = await client.fetch_course_reviews(course)
            if args.persist:
                upsert_course(hydrated_course)
                upsert_reviews(reviews)
                write_snapshot(hydrated_course, reviews)
            results.append(
                {
                    "course": hydrated_course.model_dump(mode="json"),
                    "review_count": len(reviews),
                }
            )

        print(
            json.dumps(
                {
                    "catalog_count": len(catalog),
                    "scraped_course_count": len(results),
                    "courses": results,
                },
                indent=2,
            )
        )
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(run())
