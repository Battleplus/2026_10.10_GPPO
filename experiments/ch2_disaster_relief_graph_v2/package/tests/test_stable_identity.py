import unittest
from stable_identity import encoded, key_digest, bind_decision


class IdentityTests(unittest.TestCase):
    def test_key_order_is_irrelevant_but_type_and_list_order_are_not(self):
        self.assertEqual(key_digest({'a': 0.0, 'b': True}), key_digest({'b': True, 'a': 0.0}))
        self.assertNotEqual(key_digest(0), key_digest(0.0))
        self.assertNotEqual(key_digest(False), key_digest(0.0))
        self.assertNotEqual(key_digest(['a', 'b']), key_digest(['b', 'a']))

    def test_nonfinite_and_implicit_conversions_rejected(self):
        for value in (float('nan'), float('inf'), (1, 2), {1: 'x'}):
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                encoded(value)

    def test_binding_is_public_only_and_changes_on_public_change(self):
        public = {'time': 0, 'tasks': []}
        candidates = [{'id': 'NOOP'}]
        binding = bind_decision(public, candidates)
        self.assertEqual(set(binding), {'schema', 'observation_sha256', 'candidate_catalog_sha256'})
        self.assertNotEqual(binding, bind_decision({'time': 1, 'tasks': []}, candidates))


if __name__ == '__main__':
    unittest.main()
