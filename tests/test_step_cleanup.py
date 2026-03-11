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

_main = importlib.import_module('erikbuild-FusionOrphanBodyFinder')


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


if __name__ == '__main__':
    unittest.main()
