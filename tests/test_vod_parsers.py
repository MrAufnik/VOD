import unittest

from scripts.vodlib.core import absolute, assignment_json, clean_title, embedded_json, load_config
from scripts.stages.validate import walk_catalog


class CoreParserTests(unittest.TestCase):
    def test_embedded_json_handles_nested_objects_and_braces_in_strings(self):
        html = """
        <html><script>
        window.data_query = {"outer":{"label":"a } brace","items":[{"id":1},{"id":2}]}};
        window.data_query;
        </script></html>
        """
        payloads = embedded_json(html)
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["outer"]["items"][1]["id"], 2)

    def test_assignment_json_supports_colon_and_equals(self):
        html = 'const page = { digitalSeries: [{"Url":"/show/"}] };'
        self.assertEqual(assignment_json(html, "digitalSeries")[0][0]["Url"], "/show/")
        html = 'window.data_query = {"ok":true};'
        self.assertTrue(assignment_json(html, "window.data_query")[0]["ok"])

    def test_absolute_url_preserves_absolute_and_resolves_relative(self):
        self.assertEqual(absolute("https://example.com/a/", "../b"), "https://example.com/b")
        self.assertEqual(absolute("https://example.com/a/", "https://cdn.example/x.jpg"),
                         "https://cdn.example/x.jpg")

    def test_clean_title_removes_known_poster_suffixes(self):
        self.assertEqual(clean_title("My_Show Poster Image Small"), "My Show")

    def test_all_requested_channels_are_configured(self):
        channels = load_config()["channels"]
        self.assertEqual(set(channels), {"11", "12", "13", "23", "24"})


class CatalogValidationTests(unittest.TestCase):
    def test_empty_catalog_is_counted_as_empty(self):
        stats, errors, invalid = walk_catalog({"categories": []})
        self.assertEqual(stats["series"], 0)
        self.assertEqual(stats["episodes"], 0)
        self.assertEqual(errors, [])
        self.assertEqual(invalid, [])

    def test_valid_nested_catalog_is_counted(self):
        source = {"categories": [{
            "id": "all",
            "series": [{
                "title": "Show", "url": "https://example.com/show/",
                "seasons": [{
                    "title": "Season 1",
                    "episodes": [{"title": "Episode 1", "url": "https://example.com/ep/"}]
                }]
            }]
        }]}
        stats, errors, invalid = walk_catalog(source)
        self.assertEqual((stats["series"], stats["seasons"], stats["episodes"]), (1, 1, 1))
        self.assertEqual(errors, [])
        self.assertEqual(invalid, [])


if __name__ == "__main__":
    unittest.main()
