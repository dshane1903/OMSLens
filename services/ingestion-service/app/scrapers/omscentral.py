import hashlib
import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from shared.schemas.models import CourseCatalogEntry, CourseReview
from shared.utils.text import normalize_text

if TYPE_CHECKING:
    from shared.utils.config import Settings


RSC_PUSH_PREFIX = "self.__next_f.push("
COURSES_MARKER = '"courses":['


def build_review_document_id(course_slug: str, source_document_id: str) -> str:
    return f"omscentral-review-{course_slug}-{source_document_id}"


def build_review_source_document_id(
    course_slug: str,
    author: str,
    published_at: datetime | None,
    content: str,
) -> str:
    timestamp = published_at.isoformat() if published_at else "unknown-date"
    digest = hashlib.sha256(
        f"{course_slug}|{author}|{timestamp}|{content}".encode("utf-8")
    ).hexdigest()[:16]
    return digest


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_float(value: str | None) -> float | None:
    if not value:
        return None

    cleaned = value.strip().replace("hours / week", "").replace("hrs / week", "")
    cleaned = cleaned.replace("/ 5", "").strip()
    if cleaned == "N/A":
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None

    return float(match.group())


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def extract_json_array(payload: str, marker: str) -> list[dict[str, Any]]:
    marker_index = payload.find(marker)
    if marker_index == -1:
        raise ValueError(f"Unable to locate marker {marker!r} in payload.")

    start = marker_index + len(marker) - 1
    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(payload)):
        char = payload[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return json.loads(payload[start : index + 1])

    raise ValueError(f"Unable to close JSON array for marker {marker!r}.")


def extract_rsc_payloads(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    payloads: list[str] = []

    for script in soup.find_all("script"):
        text = script.get_text().strip().removesuffix(";")
        if not text.startswith(RSC_PUSH_PREFIX):
            continue

        inner = text[len(RSC_PUSH_PREFIX) : -1]
        try:
            data = json.loads(inner)
        except json.JSONDecodeError:
            continue

        if len(data) >= 2 and isinstance(data[1], str):
            payloads.append(data[1])

    return payloads


def parse_catalog_html(html: str, base_url: str) -> list[CourseCatalogEntry]:
    payloads = extract_rsc_payloads(html)
    catalog_payload = next(
        (payload for payload in payloads if COURSES_MARKER in payload),
        None,
    )
    if not catalog_payload:
        raise ValueError("Unable to locate OMSCentral course catalog payload.")

    raw_courses = extract_json_array(catalog_payload, COURSES_MARKER)
    entries: list[CourseCatalogEntry] = []

    for course in raw_courses:
        syllabus = course.get("syllabus") or {}
        syllabus_url = syllabus.get("url")
        entries.append(
            CourseCatalogEntry(
                course_id=course["id"],
                slug=course["slug"],
                name=course["name"],
                codes=course.get("codes") or [],
                credit_hours=course.get("creditHours"),
                description=course.get("description"),
                rating=course.get("rating")
                if isinstance(course.get("rating"), (int, float))
                else None,
                difficulty=course.get("difficulty")
                if isinstance(course.get("difficulty"), (int, float))
                else None,
                workload=course.get("workload")
                if isinstance(course.get("workload"), (int, float))
                else None,
                review_count=course.get("reviewCount") or 0,
                official_url=course.get("officialURL"),
                syllabus_url=syllabus_url,
                metadata={
                    "program_refs": [
                        program.get("_ref")
                        for program in course.get("programs", [])
                        if isinstance(program, dict) and program.get("_ref")
                    ],
                    "tags": course.get("tags") or [],
                    "is_foundational": course.get("isFoundational", False),
                    "is_deprecated": course.get("isDeprecated", False),
                    "source_url": urljoin(base_url, f"/courses/{course['slug']}/reviews"),
                },
            )
        )

    return entries


def parse_course_metadata(page: BeautifulSoup, course_url: str) -> dict[str, Any]:
    quick_facts: dict[str, Any] = {}
    facts_panel = page.find("dl")
    if not facts_panel:
        return quick_facts

    for row in facts_panel.find_all("div", recursive=False):
        dt = row.find("dt")
        dd = row.find("dd")
        if not dt or not dd:
            continue

        label = normalize_text(dt.get_text(" ", strip=True)).lower()
        if label == "name":
            quick_facts["name"] = normalize_text(dd.get_text(" ", strip=True))
        elif label == "listed as":
            quick_facts["codes"] = [
                code.strip()
                for code in re.split(
                    r"\s+and\s+|,\s*",
                    normalize_text(dd.get_text(" ", strip=True)),
                )
                if code.strip()
            ]
        elif label == "credit hours":
            credit_hours = parse_float(dd.get_text(" ", strip=True))
            quick_facts["credit_hours"] = int(credit_hours) if credit_hours is not None else None
        elif label == "available to":
            quick_facts["available_to"] = normalize_text(dd.get_text(" ", strip=True))
        elif label == "description":
            quick_facts["description"] = normalize_text(dd.get_text(" ", strip=True))
        elif label == "syllabus":
            syllabus_link = dd.find("a")
            quick_facts["syllabus_url"] = syllabus_link["href"] if syllabus_link else None
        elif label == "textbooks":
            textbook_items = [
                normalize_text(item.get_text(" ", strip=True))
                for item in dd.find_all("li")
                if normalize_text(item.get_text(" ", strip=True))
            ]
            if not textbook_items:
                textbook_text = normalize_text(dd.get_text(" ", strip=True))
                textbook_items = [] if textbook_text == "No textbooks found." else [textbook_text]
            quick_facts["textbooks"] = textbook_items

    quick_facts["url"] = course_url
    return quick_facts


def article_content(article: Tag) -> str:
    body = article.find("div", class_=lambda value: value and "wrap-break-word" in value)
    if not body:
        return ""
    return normalize_text(body.get_text("\n", strip=True))


def parse_review_badges(article: Tag) -> dict[str, float | None]:
    badge_values = {
        "rating": None,
        "difficulty": None,
        "workload_hours": None,
    }

    for badge in article.select("p.flex.flex-row.gap-2 span"):
        text = normalize_text(badge.get_text(" ", strip=True))
        if text.startswith("Rating:"):
            badge_values["rating"] = parse_float(text)
        elif text.startswith("Difficulty:"):
            badge_values["difficulty"] = parse_float(text)
        elif text.startswith("Workload:"):
            badge_values["workload_hours"] = parse_float(text)

    return badge_values


def parse_course_reviews(
    html: str,
    catalog_entry: CourseCatalogEntry,
    course_url: str,
) -> tuple[CourseCatalogEntry, list[CourseReview]]:
    soup = BeautifulSoup(html, "html.parser")
    metadata = parse_course_metadata(soup, course_url)

    merged_catalog = catalog_entry.model_copy(
        update={
            "codes": metadata.get("codes", catalog_entry.codes),
            "credit_hours": metadata.get("credit_hours", catalog_entry.credit_hours),
            "description": metadata.get("description", catalog_entry.description),
            "syllabus_url": metadata.get("syllabus_url", catalog_entry.syllabus_url),
            "metadata": {
                **catalog_entry.metadata,
                "available_to": metadata.get("available_to"),
                "textbooks": metadata.get("textbooks", []),
                "course_url": course_url,
            },
        }
    )

    reviews: list[CourseReview] = []
    for article in soup.find_all("article"):
        author_node = article.select_one("span.font-medium")
        time_node = article.find("time")
        term_node = article.find("span", class_=lambda value: value and "capitalize" in value)
        body_text = article_content(article)
        if not author_node or not body_text:
            continue

        published_at = parse_datetime(time_node.get("datetime") if time_node else None)
        author = normalize_text(author_node.get_text(" ", strip=True))
        source_document_id = build_review_source_document_id(
            merged_catalog.slug,
            author,
            published_at,
            body_text,
        )
        stats = parse_review_badges(article)

        reviews.append(
            CourseReview(
                document_id=build_review_document_id(merged_catalog.slug, source_document_id),
                source_document_id=source_document_id,
                course_id=merged_catalog.course_id,
                course_slug=merged_catalog.slug,
                course_name=merged_catalog.name,
                course_codes=merged_catalog.codes,
                author=author,
                semester=normalize_text(term_node.get_text(" ", strip=True)) if term_node else None,
                published_at=published_at,
                rating=stats["rating"],
                difficulty=stats["difficulty"],
                workload_hours=stats["workload_hours"],
                url=course_url,
                title=f"{merged_catalog.name} review by {author}",
                content=body_text,
                content_hash=content_hash(body_text),
                metadata={
                    "syllabus_url": merged_catalog.syllabus_url,
                },
            )
        )

    return merged_catalog, reviews


class OMSCentralClient:
    def __init__(self, settings: "Settings") -> None:
        import httpx

        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.omscentral_base_url,
            timeout=settings.omscentral_request_timeout_seconds,
            headers={"User-Agent": settings.omscentral_user_agent},
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch_catalog(self) -> list[CourseCatalogEntry]:
        response = await self._client.get("/")
        response.raise_for_status()
        return parse_catalog_html(response.text, self._settings.omscentral_base_url)

    async def fetch_course_reviews(
        self,
        catalog_entry: CourseCatalogEntry,
    ) -> tuple[CourseCatalogEntry, list[CourseReview]]:
        course_url = f"/courses/{catalog_entry.slug}/reviews"
        response = await self._client.get(course_url)
        response.raise_for_status()
        return parse_course_reviews(
            response.text,
            catalog_entry,
            urljoin(self._settings.omscentral_base_url, course_url),
        )
