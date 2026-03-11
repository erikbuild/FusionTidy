# ABOUTME: Tests for the .step/.STEP name cleanup feature.
# ABOUTME: Covers the strip_step_extension helper and find_step_names tree traversal.

import unittest
import sys
import os
import importlib
from unittest.mock import MagicMock

# Mock the adsk modules before importing the main module
for mod_name in ['adsk', 'adsk.core', 'adsk.fusion']:
    sys.modules[mod_name] = MagicMock()

_PROJECT_DIR = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, _PROJECT_DIR)

_main = importlib.import_module('erikbuild-FusionTidy')


class TestStripStepExtension(unittest.TestCase):
    def test_suffix_lowercase(self):
        self.assertEqual(_main.strip_step_extension('Part1.step'), 'Part1')

    def test_suffix_uppercase(self):
        self.assertEqual(_main.strip_step_extension('Part1.STEP'), 'Part1')

    def test_suffix_mixed_case(self):
        self.assertEqual(_main.strip_step_extension('Part1.Step'), 'Part1')

    def test_middle_of_name(self):
        self.assertEqual(_main.strip_step_extension('FooBar.step (1)'), 'FooBar (1)')

    def test_middle_uppercase(self):
        self.assertEqual(_main.strip_step_extension('FooBar.STEP (1)'), 'FooBar (1)')

    def test_no_step(self):
        self.assertEqual(_main.strip_step_extension('NormalPart'), 'NormalPart')

    def test_empty_string(self):
        self.assertEqual(_main.strip_step_extension(''), '')

    def test_step_only(self):
        self.assertEqual(_main.strip_step_extension('.step'), '')

    def test_multiple_occurrences(self):
        self.assertEqual(_main.strip_step_extension('foo.step.step'), 'foo')

    def test_step_with_number_suffix(self):
        self.assertEqual(_main.strip_step_extension('Assembly.STEP v2'), 'Assembly v2')

    def test_does_not_strip_partial_match(self):
        self.assertEqual(_main.strip_step_extension('stepwise'), 'stepwise')

    def test_does_not_strip_footstep(self):
        self.assertEqual(_main.strip_step_extension('footstep'), 'footstep')


class MockBody:
    def __init__(self, name):
        self.name = name


class MockBodyCollection:
    def __init__(self, bodies):
        self._bodies = bodies

    @property
    def count(self):
        return len(self._bodies)

    def __iter__(self):
        return iter(self._bodies)


class MockOccurrence:
    def __init__(self, component):
        self.component = component


class MockOccurrenceList:
    def __init__(self, occurrences):
        self._occurrences = occurrences

    @property
    def count(self):
        return len(self._occurrences)

    def __iter__(self):
        return iter(self._occurrences)


class MockComponent:
    def __init__(self, name, bodies=None, children=None):
        self.name = name
        self.bRepBodies = MockBodyCollection(bodies or [])
        self.occurrences = MockOccurrenceList(children or [])

    @property
    def entityToken(self):
        return id(self)

    @property
    def allOccurrences(self):
        result = []
        for occ in self.occurrences:
            result.append(occ)
            result.extend(occ.component.allOccurrences)
        return result


class TestFindStepNames(unittest.TestCase):
    def test_finds_component_with_step_name(self):
        child = MockComponent('Leaf', bodies=[MockBody('body1')])
        step_comp = MockComponent('Part.step', bodies=[MockBody('b1')],
                                  children=[MockOccurrence(child)])
        root = MockComponent('Root', children=[MockOccurrence(step_comp)])

        results = _main.find_step_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Part.step', 'component'), names)

    def test_finds_body_with_step_name(self):
        step_body = MockBody('Bracket.STEP (1)')
        comp = MockComponent('CleanComp', bodies=[step_body])
        root = MockComponent('Root', children=[MockOccurrence(comp)])

        results = _main.find_step_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Bracket.STEP (1)', 'body'), names)

    def test_no_matches(self):
        comp = MockComponent('Clean', bodies=[MockBody('NormalBody')])
        root = MockComponent('Root', children=[MockOccurrence(comp)])

        results = _main.find_step_names(root)
        self.assertEqual(results, [])

    def test_includes_root_component(self):
        root = MockComponent('Assembly.step', bodies=[MockBody('clean')])
        results = _main.find_step_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Assembly.step', 'component'), names)

    def test_includes_root_body(self):
        root = MockComponent('Root', bodies=[MockBody('Part.STEP')])
        results = _main.find_step_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Part.STEP', 'body'), names)


class TestStripSpecialChars(unittest.TestCase):
    def test_strips_curly_braces(self):
        self.assertEqual(_main.strip_special_chars('Part{1}'), 'Part1')

    def test_strips_angle_brackets(self):
        self.assertEqual(_main.strip_special_chars('Asm<v2>'), 'Asmv2')

    def test_preserves_allowed_chars(self):
        self.assertEqual(_main.strip_special_chars('Part-1 (A) [B] #3.step'), 'Part-1 (A) [B] #3.step')

    def test_strips_at_sign(self):
        self.assertEqual(_main.strip_special_chars('user@domain'), 'userdomain')

    def test_strips_mixed_special(self):
        self.assertEqual(_main.strip_special_chars('Bolt M6×1.0 {rev}'), 'Bolt M61.0 rev')

    def test_empty_string(self):
        self.assertEqual(_main.strip_special_chars(''), '')

    def test_all_allowed(self):
        name = 'Normal Part-2 (copy) [rev] #5.stp'
        self.assertEqual(_main.strip_special_chars(name), name)

    def test_preserves_plus(self):
        self.assertEqual(_main.strip_special_chars('A+B'), 'A+B')

    def test_strips_equals(self):
        self.assertEqual(_main.strip_special_chars('A=B'), 'AB')

    def test_preserves_digits(self):
        self.assertEqual(_main.strip_special_chars('12345'), '12345')

    def test_preserves_underscores(self):
        self.assertEqual(_main.strip_special_chars('Part_1_rev'), 'Part_1_rev')


class TestHasSpecialChars(unittest.TestCase):
    def test_clean_name(self):
        self.assertFalse(_main.has_special_chars('Part-1 (A) [B] #3.step'))

    def test_dirty_name(self):
        self.assertTrue(_main.has_special_chars('Part{1}'))

    def test_empty_string(self):
        self.assertFalse(_main.has_special_chars(''))


class TestFindSpecialCharNames(unittest.TestCase):
    def test_finds_component_with_special_chars(self):
        child = MockComponent('Leaf', bodies=[MockBody('body1')])
        bad_comp = MockComponent('Part{1}', bodies=[MockBody('b1')],
                                 children=[MockOccurrence(child)])
        occ = MockOccurrence(bad_comp)
        root = MockComponent('Root', children=[occ])

        results = _main.find_special_char_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Part{1}', 'component'), names)
        match = [r for r in results if r['name'] == 'Part{1}'][0]
        self.assertIs(match['occurrence'], occ)

    def test_finds_body_with_special_chars(self):
        bad_body = MockBody('Bracket<v2>')
        comp = MockComponent('CleanComp', bodies=[bad_body])
        root = MockComponent('Root', children=[MockOccurrence(comp)])

        results = _main.find_special_char_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Bracket<v2>', 'body'), names)

    def test_no_matches(self):
        comp = MockComponent('Clean', bodies=[MockBody('Normal Body')])
        root = MockComponent('Root', children=[MockOccurrence(comp)])

        results = _main.find_special_char_names(root)
        self.assertEqual(results, [])

    def test_includes_root_component(self):
        root = MockComponent('Assembly{bad}', bodies=[MockBody('clean')])
        results = _main.find_special_char_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Assembly{bad}', 'component'), names)
        match = [r for r in results if r['name'] == 'Assembly{bad}'][0]
        self.assertIsNone(match['occurrence'])

    def test_includes_root_body(self):
        root = MockComponent('Root', bodies=[MockBody('Part<1>')])
        results = _main.find_special_char_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Part<1>', 'body'), names)


class TestStripVersionNumber(unittest.TestCase):
    def test_suffix(self):
        self.assertEqual(_main.strip_version_number('Part v1'), 'Part')

    def test_suffix_double_digit(self):
        self.assertEqual(_main.strip_version_number('Bracket v12'), 'Bracket')

    def test_middle_of_name(self):
        self.assertEqual(_main.strip_version_number('Part v3 (copy)'), 'Part (copy)')

    def test_no_space_before(self):
        self.assertEqual(_main.strip_version_number('Partv2'), 'Partv2')

    def test_uppercase_v(self):
        self.assertEqual(_main.strip_version_number('Part V2'), 'Part')

    def test_no_version(self):
        self.assertEqual(_main.strip_version_number('Normal Part'), 'Normal Part')

    def test_empty_string(self):
        self.assertEqual(_main.strip_version_number(''), '')

    def test_multiple_versions(self):
        self.assertEqual(_main.strip_version_number('Part v1 v2'), 'Part')

    def test_preserves_v_in_words(self):
        self.assertEqual(_main.strip_version_number('Valve'), 'Valve')

    def test_v_followed_by_non_digit(self):
        self.assertEqual(_main.strip_version_number('Part vX'), 'Part vX')

    def test_cleans_extra_spaces(self):
        self.assertEqual(_main.strip_version_number('Part  v1  end'), 'Part end')


class TestHasVersionNumber(unittest.TestCase):
    def test_has_version(self):
        self.assertTrue(_main.has_version_number('Part v1'))

    def test_no_version(self):
        self.assertFalse(_main.has_version_number('Normal Part'))

    def test_empty_string(self):
        self.assertFalse(_main.has_version_number(''))

    def test_v_in_word(self):
        self.assertFalse(_main.has_version_number('Valve'))


class TestFindVersionNumberNames(unittest.TestCase):
    def test_finds_component_with_version(self):
        child = MockComponent('Leaf', bodies=[MockBody('body1')])
        ver_comp = MockComponent('Part v2', bodies=[MockBody('b1')],
                                 children=[MockOccurrence(child)])
        occ = MockOccurrence(ver_comp)
        root = MockComponent('Root', children=[occ])

        results = _main.find_version_number_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Part v2', 'component'), names)
        match = [r for r in results if r['name'] == 'Part v2'][0]
        self.assertIs(match['occurrence'], occ)

    def test_finds_body_with_version(self):
        ver_body = MockBody('Bracket V3')
        comp = MockComponent('CleanComp', bodies=[ver_body])
        root = MockComponent('Root', children=[MockOccurrence(comp)])

        results = _main.find_version_number_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Bracket V3', 'body'), names)

    def test_no_matches(self):
        comp = MockComponent('Clean', bodies=[MockBody('Normal Body')])
        root = MockComponent('Root', children=[MockOccurrence(comp)])

        results = _main.find_version_number_names(root)
        self.assertEqual(results, [])

    def test_includes_root_component(self):
        root = MockComponent('Assembly v1', bodies=[MockBody('clean')])
        results = _main.find_version_number_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Assembly v1', 'component'), names)
        match = [r for r in results if r['name'] == 'Assembly v1'][0]
        self.assertIsNone(match['occurrence'])

    def test_includes_root_body(self):
        root = MockComponent('Root', bodies=[MockBody('Part v5')])
        results = _main.find_version_number_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Part v5', 'body'), names)


class TestStripCopySuffixes(unittest.TestCase):
    def test_single_suffix(self):
        self.assertEqual(_main.strip_copy_suffixes('Part (1)'), 'Part')

    def test_multiple_stacked(self):
        self.assertEqual(_main.strip_copy_suffixes('M3x8 BHCS (15) (1) (1)'), 'M3x8 BHCS')

    def test_double_suffix(self):
        self.assertEqual(_main.strip_copy_suffixes('Bracket (3) (2)'), 'Bracket')

    def test_no_suffix(self):
        self.assertEqual(_main.strip_copy_suffixes('Normal Part'), 'Normal Part')

    def test_empty_string(self):
        self.assertEqual(_main.strip_copy_suffixes(''), '')

    def test_preserves_non_trailing_parens(self):
        self.assertEqual(_main.strip_copy_suffixes('Part (A) Detail'), 'Part (A) Detail')

    def test_mixed_trailing_parens(self):
        self.assertEqual(_main.strip_copy_suffixes('Part (A) (1)'), 'Part (A)')

    def test_large_number(self):
        self.assertEqual(_main.strip_copy_suffixes('Bolt (123)'), 'Bolt')

    def test_preserves_parens_with_text(self):
        self.assertEqual(_main.strip_copy_suffixes('Part (copy)'), 'Part (copy)')


class TestHasCopySuffixes(unittest.TestCase):
    def test_has_suffix(self):
        self.assertTrue(_main.has_copy_suffixes('Part (1)'))

    def test_stacked(self):
        self.assertTrue(_main.has_copy_suffixes('Part (3) (1)'))

    def test_no_suffix(self):
        self.assertFalse(_main.has_copy_suffixes('Normal Part'))

    def test_empty_string(self):
        self.assertFalse(_main.has_copy_suffixes(''))

    def test_non_numeric_parens(self):
        self.assertFalse(_main.has_copy_suffixes('Part (copy)'))


class TestFindCopySuffixNames(unittest.TestCase):
    def test_finds_component_with_suffix(self):
        child = MockComponent('Leaf', bodies=[MockBody('body1')])
        bad_comp = MockComponent('Part (1)', bodies=[MockBody('b1')],
                                 children=[MockOccurrence(child)])
        occ = MockOccurrence(bad_comp)
        root = MockComponent('Root', children=[occ])

        results = _main.find_copy_suffix_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Part (1)', 'component'), names)
        match = [r for r in results if r['name'] == 'Part (1)'][0]
        self.assertIs(match['occurrence'], occ)

    def test_finds_body_with_suffix(self):
        bad_body = MockBody('Bracket (3) (2)')
        comp = MockComponent('CleanComp', bodies=[bad_body])
        root = MockComponent('Root', children=[MockOccurrence(comp)])

        results = _main.find_copy_suffix_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Bracket (3) (2)', 'body'), names)

    def test_no_matches(self):
        comp = MockComponent('Clean', bodies=[MockBody('Normal Body')])
        root = MockComponent('Root', children=[MockOccurrence(comp)])

        results = _main.find_copy_suffix_names(root)
        self.assertEqual(results, [])

    def test_includes_root_component(self):
        root = MockComponent('Assembly (1)', bodies=[MockBody('clean')])
        results = _main.find_copy_suffix_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Assembly (1)', 'component'), names)
        match = [r for r in results if r['name'] == 'Assembly (1)'][0]
        self.assertIsNone(match['occurrence'])

    def test_includes_root_body(self):
        root = MockComponent('Root', bodies=[MockBody('Part (5)')])
        results = _main.find_copy_suffix_names(root)
        names = [(r['name'], r['kind']) for r in results]
        self.assertIn(('Part (5)', 'body'), names)


if __name__ == '__main__':
    unittest.main()
