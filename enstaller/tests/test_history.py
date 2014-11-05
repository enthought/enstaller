from os.path import dirname, join, isfile
from os import unlink

from egginst.vendor.six.moves import unittest

from enstaller.history import History


PATH = join(dirname(__file__), 'history')


def package_changes(first_set, second_set):
    removed = ['-' + name for name in first_set - second_set]
    added = ['+' + name for name in second_set - first_set]
    return set(removed + added)


class TestHistory(unittest.TestCase):

    def setUp(self):
        self.history = History('<dummy prefix>')
        self.history._log_path = PATH
        self.package_sets = [set(['appinst-2.1.0-1.egg',
                                  'basemap-1.0.1-1.egg',
                                  'biopython-1.57-2.egg']),

                             set(['basemap-1.0.2-1.egg',
                                  'biopython-1.57-2.egg',
                                  'numpy-1.6.1-2.egg']),

                             set(['basemap-1.0.2-1.egg',
                                  'biopython-1.57-2.egg',
                                  'numpy-1.7.0-1.egg'])]
        # Write the history file
        self.history._write_egg_names(self.package_sets[0])
        for i, state in enumerate(self.package_sets[:-1]):
            self.history._write_changes(state, self.package_sets[i+1])

    def tearDown(self):
        if isfile(self.history._log_path):
            unlink(self.history._log_path)

    def test_get_state(self):
        self.assertEqual(self.history.get_state(0), self.package_sets[0])
        self.assertEqual(self.history.get_state(), self.package_sets[-1])

    def test_parse(self):
        package_edits = [packages for (date, packages) in self.history.parse()]
        self.assertEqual(self.package_sets[0], package_edits[0])
        self.assertEqual(package_changes(self.package_sets[0],
                                         self.package_sets[1]),
                         package_edits[1])
        self.history.print_log()

        # When history file is not present
        unlink(self.history._log_path)
        self.assertEqual(self.history.parse(), [])
        self.history.print_log()

    def test_update(self):
        self.history.update()
        self.assertEqual(self.history.get_state(), set())
        self.assertEqual(self.history.parse()[-1][1],
                         package_changes(self.package_sets[-1], set()))

if __name__ == '__main__':
    unittest.main()
