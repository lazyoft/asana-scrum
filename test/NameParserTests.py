import unittest

from asanatools.NameParser import NameParser


class NameParserTests(unittest.TestCase):
    def test_glob(self):
        from pathlib import Path
        print("Ciao")
        for path in Path('/Users/brizio').rglob('*'):
            print(path.name)


    def test_name(self):
        self.assertEqual(NameParser("Name (abbreviation)").name, "Name")
        self.assertEqual(NameParser("Name").name, "Name")
        self.assertEqual(NameParser("Name > Subordinate").name, "Name")
        self.assertEqual(NameParser("Name (abbreviation) > Subordinate").name, "Name")
        self.assertEqual(NameParser("Name > Subordinate (abbreviation)").name, "Name")

    def test_abbreviation(self):
        self.assertEqual(NameParser("Name (abbreviation)").abbreviation, "abbreviation")
        self.assertEqual(NameParser("Name").abbreviation, None)
        self.assertEqual(NameParser("Name > Subordinate").abbreviation, None)
        self.assertEqual(NameParser("Name (abbreviation) > Subordinate").abbreviation, "abbreviation")
        self.assertEqual(NameParser("Name > Subordinate (abbreviation)").abbreviation, None)

    def test_mnemonic(self):
        self.assertEqual(NameParser("Name (abbreviation)").mnemonic, "abbreviation")
        self.assertEqual(NameParser("Name").mnemonic, "Name")
        self.assertEqual(NameParser("Name > Subordinate").mnemonic, "Name")
        self.assertEqual(NameParser("Name (abbreviation) > Subordinate").mnemonic, "abbreviation")
        self.assertEqual(NameParser("Name > Subordinate (abbreviation)").mnemonic, "Name")

    def test_untagged(self):
        self.assertEqual(NameParser("Name").untagged, "Name")
        self.assertEqual(NameParser("[Tags] Name (abbreviation)").untagged, "Name (abbreviation)")
        self.assertEqual(NameParser("[Tags] Name (abbreviation) > Subordinate").untagged, "Name (abbreviation) > Subordinate")
        self.assertEqual(NameParser("[Tags] Name (abbreviation) > Subordinate (abbreviation)").untagged,
                         "Name (abbreviation) > Subordinate (abbreviation)")
        self.assertEqual(NameParser("[Tags]  Name (abbreviation) > Subordinate (abbreviation)").untagged,
                         "Name (abbreviation) > Subordinate (abbreviation)")

    def test_matches(self):
        self.assertTrue(NameParser("Name").matches("Name"))
        self.assertTrue(NameParser("Name (abbreviation)").matches("Name (abbreviation)"))
        self.assertTrue(NameParser("Name (abbreviation)").matches("Name"))
        self.assertTrue(NameParser("Name (abbreviation)").matches("abbreviation"))
        self.assertFalse(NameParser("Name > Subordinate").matches("Name"))
        self.assertFalse(NameParser("Name (abbreviation) > Subordinate").matches("Name (abbreviation)"))
        self.assertFalse(NameParser("Name (abbreviation) > Subordinate").matches("Name"))
        self.assertFalse(NameParser("Name (abbreviation) > Subordinate").matches("abbreviation"))


if __name__ == '__main__':
    unittest.main()
