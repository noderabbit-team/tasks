import datetime
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
        self.assertEqual(log.logtype, ZoomDatabase.LOG_INFO)

    def test_add_bundle(self):
        """Verify adding a bundle location."""
        app_db_id = 100
        bundle_name = "p00100_foobar_bundle_20110206_001"
        bundle_location = "s3:somebucket:" + bundle_name
        code_revision = "e4397ee07a644d0086aa-b03b72390a99"

        self.assertEqual(self.soup.dz2_appbundle.count(), 0,
                         "Start out with no appbundles in DB")

        self.zoom_db.add_bundle(app_db_id,
                                bundle_name,
                                bundle_location,
                                code_revision)

        self.assertEqual(self.soup.dz2_appbundle.count(), 1)

        bundle_from_db = list(self.soup.dz2_appbundle.all())[0]

        self.assertEqual(bundle_from_db.project_id, app_db_id)
        self.assertEqual(bundle_from_db.bundle_name, bundle_name)
        self.assertEqual(bundle_from_db.bundle_location, bundle_location)
        self.assertEqual(bundle_from_db.code_revision, code_revision)
        self.assertTrue((datetime.datetime.utcnow() - 
                         bundle_from_db.creation_date
                         ) < datetime.timedelta(seconds=1))

    def test_get_bundle(self):
        """Get bundle by ID"""
        bundle_id = 100
        self.soup.dz2_appbundle.insert(
            id=bundle_id,
            project_id=1,
            bundle_name="a_bundle_name",
            bundle_location="a_bundle_location",
            code_revision="a_code_revision",
            creation_date=datetime.datetime.utcnow())

        self.assertEqual(self.soup.dz2_appbundle.count(), 1)

        bundle_from_zoomdb = self.zoom_db.get_bundle(bundle_id)

        self.assertEqual(bundle_from_zoomdb.id, bundle_id)
        self.assertEqual(bundle_from_zoomdb.bundle_name, "a_bundle_name")

    def test_add_worker(self):
        """Record addition of a worker for an appbundle in DB."""
        app_db_id = 100
        bundle_id = 200
        instance_id = "i-asdoasdf"
        server_ip = "10.0.100.210"
        server_port = 10230

        self.assertEqual(self.soup.dz2_appserverdeployment.count(), 0)

        self.zoom_db.add_worker(app_db_id,
                                bundle_id,
                                instance_id,
                                server_ip,
                                server_port)

        self.assertEqual(self.soup.dz2_appserverdeployment.count(), 1)
        worker_deployment_record = list(
            self.soup.dz2_appserverdeployment.all())[0]
        self.assertEqual(worker_deployment_record.project_id, app_db_id)
        self.assertEqual(worker_deployment_record.bundle_id, bundle_id)
        self.assertEqual(worker_deployment_record.server_instance_id, instance_id)
        self.assertEqual(worker_deployment_record.server_ip, server_ip)
        self.assertEqual(worker_deployment_record.server_port, server_port)