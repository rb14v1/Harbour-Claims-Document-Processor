from django.test import TestCase

from apps.common import search_store


class SearchStoreStubTests(TestCase):
    def setUp(self):
        search_store.reset_memory_store()

    def tearDown(self):
        search_store.reset_memory_store()

    def test_upsert_and_search_returns_top_k_by_similarity(self):
        items = [
            {"id": "a", "vector": [1.0, 0.0], "payload": {"claim_id": 1}},
            {"id": "b", "vector": [0.0, 1.0], "payload": {"claim_id": 2}},
            {"id": "c", "vector": [0.9, 0.1], "payload": {"claim_id": 3}},
        ]
        search_store.upsert_chunks("test-index", items)

        results = search_store.search("test-index", [1.0, 0.0], top_k=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], "a")
        self.assertAlmostEqual(results[0]["score"], 1.0, places=4)
        self.assertEqual(results[1]["id"], "c")

    def test_search_excludes_ids(self):
        items = [
            {"id": "a", "vector": [1.0, 0.0], "payload": {}},
            {"id": "b", "vector": [1.0, 0.0], "payload": {}},
        ]
        search_store.upsert_chunks("test-index", items)

        results = search_store.search("test-index", [1.0, 0.0], top_k=5, exclude_ids={"a"})
        ids = [r["id"] for r in results]
        self.assertNotIn("a", ids)
        self.assertIn("b", ids)

    def test_upsert_replaces_existing_id(self):
        search_store.upsert_chunks("test-index", [{"id": "a", "vector": [1.0, 0.0], "payload": {"v": 1}}])
        search_store.upsert_chunks("test-index", [{"id": "a", "vector": [0.0, 1.0], "payload": {"v": 2}}])

        results = search_store.search("test-index", [0.0, 1.0], top_k=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["payload"]["v"], 2)

    def test_search_on_unknown_index_returns_empty(self):
        results = search_store.search("does-not-exist", [1.0, 0.0])
        self.assertEqual(results, [])

    def test_zero_vector_similarity_is_zero(self):
        search_store.upsert_chunks("test-index", [{"id": "a", "vector": [0.0, 0.0], "payload": {}}])
        results = search_store.search("test-index", [1.0, 0.0], top_k=5)
        self.assertEqual(results[0]["score"], 0.0)
