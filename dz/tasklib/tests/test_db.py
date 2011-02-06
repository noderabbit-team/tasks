import os

from mocker import MockerTestCase

from sqlalchemy.ext.sqlsoup import SqlSoup
from sqlalchemy import create_engine

from dz.tasklib.db import ZoomDatabase


class ZoomDatabaseTest(MockerTestCase):

    def setUp(self):
        self.db = create_engine("sqlite://")
        ddl = open(
            os.path.join(
                os.path.dirname(__file__),
                "dz2-simplified.sql")).read().split(";")

        for statement in ddl:
            if not statement.strip():
                continue
            self.db.execute(statement)

        self.zoom_db = ZoomDatabase(self.db, 1)
        # For verifying results
        self.soup = SqlSoup(self.db)

    def test_log(self):
        """Verify that jobs can log to the database."""
        self.zoom_db.log("message")
        results = list(self.soup.dz2_log.all())
        self.assertEqual(len(results), 1)
        log = results.pop()
        self.assertEqual(log.job_id, 1)
        self.assertEqual(log.message, "message")

    def test_add_bundle(self):
        """verify add a bundle location."""
        pass
