import unittest

from app.scrapers.omscentral import parse_catalog_html, parse_course_reviews
from shared.schemas.models import CourseCatalogEntry


CATALOG_FIXTURE = """
<html>
  <body>
    <script>
      self.__next_f.push([1,"8:[\\"$\\",\\"$L12\\",null,{\\"courses\\":[{\\"id\\":\\"course-1\\",\\"slug\\":\\"software-architecture-and-design\\",\\"name\\":\\"Software Architecture and Design\\",\\"codes\\":[\\"CS-6310\\"],\\"creditHours\\":3,\\"description\\":\\"A project-based course.\\",\\"rating\\":2.95,\\"difficulty\\":2.61,\\"workload\\":11.88,\\"reviewCount\\":2,\\"officialURL\\":\\"https://omscs.gatech.edu/cs-6310\\",\\"syllabus\\":{\\"url\\":\\"https://example.com/syllabus.pdf\\"},\\"programs\\":[{\\"_ref\\":\\"program-1\\"}],\\"tags\\":[\\"SDP\\"],\\"isFoundational\\":false,\\"isDeprecated\\":false}]}]"])
    </script>
  </body>
</html>
"""


COURSE_FIXTURE = """
<html>
  <body>
    <section>
      <h3>Software Architecture and Design</h3>
      <div>
        <dl>
          <div>
            <dt>Name</dt>
            <dd>Software Architecture and Design</dd>
          </div>
          <div>
            <dt>Listed As</dt>
            <dd>CS-6310</dd>
          </div>
          <div>
            <dt>Credit Hours</dt>
            <dd>3</dd>
          </div>
          <div>
            <dt>Available to</dt>
            <dd>CS students</dd>
          </div>
          <div>
            <dt>Description</dt>
            <dd>This project-based course will cover software design.</dd>
          </div>
          <div>
            <dt>Syllabus</dt>
            <dd><a href="https://example.com/syllabus.pdf">Syllabus</a></dd>
          </div>
          <div>
            <dt>Textbooks</dt>
            <dd>No textbooks found.</dd>
          </div>
        </dl>
      </div>
      <ul>
        <li>
          <article>
            <p>
              <span class="font-medium">anon-reviewer</span>
              <span class="capitalize">spring 2026</span>
              <time datetime="2026-04-07T00:07:51Z">April 7, 2026</time>
            </p>
            <div class="wrap-break-word">
              <p>Great course with useful diagrams and manageable workload.</p>
            </div>
            <p class="flex flex-row gap-2">
              <span>Rating: 5 / 5</span>
              <span>Difficulty: 2 / 5</span>
              <span>Workload: 8 hours / week</span>
            </p>
          </article>
        </li>
      </ul>
    </section>
  </body>
</html>
"""


class OMSCentralParserTests(unittest.TestCase):
    def test_parse_catalog_html(self) -> None:
        courses = parse_catalog_html(CATALOG_FIXTURE, "https://www.omscentral.com")

        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0].slug, "software-architecture-and-design")
        self.assertEqual(courses[0].codes, ["CS-6310"])
        self.assertEqual(courses[0].review_count, 2)

    def test_parse_course_reviews(self) -> None:
        catalog_entry = CourseCatalogEntry(
            course_id="course-1",
            slug="software-architecture-and-design",
            name="Software Architecture and Design",
            codes=["CS-6310"],
            review_count=1,
        )

        course, reviews = parse_course_reviews(
            COURSE_FIXTURE,
            catalog_entry,
            "https://www.omscentral.com/courses/software-architecture-and-design/reviews",
        )

        self.assertEqual(course.syllabus_url, "https://example.com/syllabus.pdf")
        self.assertEqual(course.metadata["available_to"], "CS students")
        self.assertEqual(len(reviews), 1)
        self.assertEqual(reviews[0].author, "anon-reviewer")
        self.assertEqual(reviews[0].semester, "spring 2026")
        self.assertEqual(reviews[0].rating, 5.0)
        self.assertEqual(reviews[0].difficulty, 2.0)
        self.assertEqual(reviews[0].workload_hours, 8.0)


if __name__ == "__main__":
    unittest.main()
