import json
import os.path
import shutil
import tempfile

from egginst._compat import assertCountEqual
from egginst.vendor.six.moves import unittest

from enstaller.compat import path_to_uri
from enstaller.config import Configuration
from enstaller.legacy_stores import parse_index, repository_factory

from enstaller.tests.common import (SIMPLE_INDEX,
                                    dummy_repository_package_factory,
                                    mock_index,
                                    mocked_session_factory)


def _index_provider(store_location):
    entries = [
        dummy_repository_package_factory("numpy", "1.8.0", 1,
                                         store_location=store_location),
        dummy_repository_package_factory("scipy", "0.14.0", 1,
                                         store_location=store_location)
    ]
    return json.dumps(dict((entry.key, entry.s3index_data) for entry in entries))


class TestLegacyStores(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_simple_webservice(self):
        # Given
        store_location = ""
        body = _index_provider(store_location)

        # When
        packages = list(parse_index(json.loads(body), store_location))

        # Then
        self.assertTrue(len(packages) > 0)
        assertCountEqual(self, [p.name for p in packages], ["numpy", "scipy"])
        assertCountEqual(self, [p.full_version for p in packages], ["1.8.0-1",
                                                                    "0.14.0-1"])

    def test_simple_no_webservice_file(self):
        # Given
        fake_index = {
            "zope.testing-3.8.3-1.egg": {
                "available": True,
                "build": 1,
                "md5": "6041fd75b7fe9187ccef0d40332c6c16",
                "mtime": 1262725254.0,
                "name": "zope.testing",
                "product": "commercial",
                "python": "2.6",
                "size": 514439,
                "type": "egg",
                "version": "3.8.3",
            }
        }
        index_path = os.path.join(self.tempdir, "index.json")
        with open(index_path, "w") as fp:
            fp.write(json.dumps(fake_index))

        # When
        session = mocked_session_factory(self.tempdir)
        resp = session.fetch(path_to_uri(index_path))
        packages = list(parse_index(resp.json(), "", python_version="2.6"))

        # Then
        self.assertEqual(len(packages), 1)
        self.assertEqual(packages[0].key, "zope.testing-3.8.3-1.egg")

    def test_parse_index_python_version(self):
        # Given
        index = {
            "zope.testing-3.8.3-1.egg": {
                "available": True,
                "build": 1,
                "md5": "6041fd75b7fe9187ccef0d40332c6c16",
                "mtime": 1262725254.0,
                "name": "zope.testing",
                "product": "commercial",
                "python": "2.6",
                "size": 514439,
                "type": "egg",
                "version": "3.8.3",
            }
        }

        # When
        packages = list(parse_index(index, "", python_version="2.6"))

        # Then
        self.assertEqual(len(packages), 1)

        # When
        packages = list(parse_index(index, "", python_version="2.4"))

        # Then
        self.assertEqual(len(packages), 0)

        # When
        packages = list(parse_index(index, "", "*"))

        # Then
        self.assertEqual(len(packages), 1)

    @mock_index(SIMPLE_INDEX)
    def test_repository_factory(self):
        # Given
        config = Configuration()
        session = mocked_session_factory(self.tempdir)

        # When
        repository = repository_factory(session, config.indices)

        # Then
        self.assertEqual(len(list(repository.iter_packages())), 1)
        self.assertEqual(len(list(repository.find_packages("nose", "1.3.4-1"))), 1)
