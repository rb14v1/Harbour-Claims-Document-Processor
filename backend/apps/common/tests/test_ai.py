from django.test import TestCase

from apps.common import ai


class AiStubTests(TestCase):
    def test_chat_completion_is_deterministic(self):
        messages = [{"role": "user", "content": "Summarize this claim"}]
        first = ai.chat_completion(messages)
        second = ai.chat_completion(messages)
        self.assertEqual(first, second)
        self.assertIsInstance(first, str)
        self.assertTrue(len(first) > 0)

    def test_chat_completion_differs_for_different_input(self):
        first = ai.chat_completion([{"role": "user", "content": "claim A"}])
        second = ai.chat_completion([{"role": "user", "content": "claim B"}])
        self.assertNotEqual(first, second)

    def test_embedding_has_correct_dimensions(self):
        vector = ai.generate_embedding("a claim narrative")
        self.assertEqual(len(vector), ai.EMBEDDING_DIMENSIONS)
        self.assertTrue(all(isinstance(v, float) for v in vector))

    def test_embedding_is_deterministic(self):
        first = ai.generate_embedding("identical text")
        second = ai.generate_embedding("identical text")
        self.assertEqual(first, second)

    def test_embedding_differs_for_different_text(self):
        first = ai.generate_embedding("rear end collision")
        second = ai.generate_embedding("kitchen fire damage")
        self.assertNotEqual(first, second)

    def test_pad_vector_truncates_and_pads(self):
        self.assertEqual(len(ai.pad_vector([1.0, 2.0, 3.0], dims=2)), 2)
        padded = ai.pad_vector([1.0], dims=5)
        self.assertEqual(padded, [1.0, 0.0, 0.0, 0.0, 0.0])
