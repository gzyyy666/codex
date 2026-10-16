import unittest

from run_web_fluidity_review import apply_source_changes


class OverlayTest(unittest.TestCase):
    def test_preserves_installed_only_edits(self):
        self.assertEqual(apply_source_changes('a\nb\nc\n','a\nB\nc\n','A\nb\nc\n'),'A\nB\nc\n')

    def test_repeated_lines_need_unique_exact_context(self):
        old='english\nshared\nend-en\nchinese\nshared\nend-zh\n'
        new=old.replace('shared\n','updated\n')
        installed=old+'formal-only\n'
        self.assertEqual(apply_source_changes(old,new,installed),new+'formal-only\n')

    def test_overlapping_formal_change_rejected(self):
        with self.assertRaises(ValueError):
            apply_source_changes('a\nb\nc\n','a\nB\nc\n','a\nother\nc\n')


if __name__=='__main__':
    unittest.main()
