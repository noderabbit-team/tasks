import datetime
import os
import random

from mocker import MockerTestCase

from sqlalchemy.ext.sqlsoup import SqlSoup
from sqlalchemy import create_engine

from dz.tasklib.zoomdb import ZoomDatabase
from dz.tasklib import taskconfig


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

        # create a stub project
        self.soup.dz2_project.insert(id=2, owner_id=1, source_code_url="",
                                     title="UnitTest Project",
                                     django_version="1.2",
                                     database_type="postgresql-8.4",
                                     base_python_package="",
                                     django_settings_module="my.settings")

        # create a stub job
        self.soup.dz2_job.insert(id=1, task_id=1, jobcode="deploy",
                                 project_id=2,
                                 owner_id=1, issued_by_id=1,
                                 issued_at=datetime.datetime.utcnow())

    def test_log(self):
        """Verify that jobs can log to the database."""
        self.zoom_db.log("message")
        results = list(self.soup.dz2_log.all())
        self.assertEqual(len(results), 1)
        log = results.pop()
        self.assertEqual(log.job_id, 1)
        self.assertEqual(log.message, "message")
        self.assertEqual(log.logtype, ZoomDatabase.LOG_INFO)

        self.zoom_db.log("a warning", ZoomDatabase.LOG_WARN)
        results = list(self.soup.dz2_log.all())
        self.assertEqual(len(results), 2)
        logw = results.pop()
        self.assertEqual(logw.id, 2)
        self.assertEqual(logw.job_id, 1)
        self.assertEqual(logw.message, "a warning")
        self.assertEqual(logw.logtype, ZoomDatabase.LOG_WARN)

    def test_add_bundle(self):
        """Verify adding a bundle location."""
        app_db_id = 2
        bundle_name = "p00100_foobar_bundle_20110206_001"
        code_revision = "e4397ee07a644d0086aa-b03b72390a99"

        self.assertEqual(self.soup.dz2_appbundle.count(), 0,
                         "Start out with no appbundles in DB")

        self.zoom_db.add_bundle(bundle_name,
                                code_revision)

        self.assertEqual(self.soup.dz2_appbundle.count(), 1)

        bundle_from_db = list(self.soup.dz2_appbundle.all())[0]

        self.assertEqual(bundle_from_db.project_id, app_db_id)
        self.assertEqual(bundle_from_db.bundle_name, bundle_name)
        self.assertEqual(bundle_from_db.code_revision, code_revision)
        self.assertTrue((datetime.datetime.utcnow() -
                         bundle_from_db.creation_date)
                        < datetime.timedelta(seconds=1))

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
        app_db_id = 2
        bundle_id = 200
        instance_id = "i-asdoasdf"
        server_ip = "10.0.100.210"
        server_port = 10230

        self.assertEqual(self.soup.dz2_appserverdeployment.count(), 0)
        self.assertEqual(len(self.zoom_db.get_project_workers()), 0)

        self.zoom_db.add_worker(bundle_id,
                                instance_id,
                                server_ip,
                                server_port)

        self.assertEqual(self.soup.dz2_appserverdeployment.count(), 1)
        self.assertEqual(len(self.zoom_db.get_project_workers()), 1)

        worker_deployment_record = list(
            self.soup.dz2_appserverdeployment.all())[0]
        self.assertEqual(worker_deployment_record.project_id, app_db_id)
        self.assertEqual(worker_deployment_record.bundle_id, bundle_id)
        self.assertEqual(worker_deployment_record.server_instance_id,
                         instance_id)
        self.assertEqual(worker_deployment_record.server_ip, server_ip)
        self.assertEqual(worker_deployment_record.server_port, server_port)

    def test_search_workers(self):
        """
        Test querying with search_workers.
        """
        z = self.zoom_db

        b1 = z.add_bundle("test_bundle_1")
        b2 = z.add_bundle("test_bundle_2")

        wo1 = z.add_worker(b1.id, "test_host_1", "127.0.0.1", 11111)
        wo2 = z.add_worker(b2.id, "test_host_2", "127.0.1.0", 11112)

        ws1 = z.get_project_workers()
        ws2 = z.search_workers(active=None)
        ws1.sort(key=lambda x: x.id)
        ws2.sort(key=lambda x: x.id)

        self.assertEqual(ws1, ws2)
        self.assertEqual(len(ws2), 2)

        # now let's do some searches...
        s1 = z.search_workers(bundle_ids=[b1.id])
        self.assertEqual(len(s1), 1)
        self.assertEqual(s1[0], wo1)

        # and deactivate
        wo2.deactivation_date = datetime.datetime.utcnow()
        z.flush()
        s2 = z.search_workers(bundle_ids=[b2.id])  # active only by default!
        self.assertEqual(len(s2), 0)

        # gimme the inactive one
        s3 = z.search_workers(bundle_ids=[b2.id], active=False)
        self.assertEqual(len(s3), 1)

        # gimme both active and inactive
        s4 = z.search_workers(bundle_ids=[b2.id], active=None)
        self.assertEqual(len(s4), 1)

        # and just gimme everything active
        s5 = z.search_workers()
        self.assertEqual(len(s5), 1)
        self.assertEqual(s5[0], wo1)

    def test_get_job(self):
        """
        Get the job associated with current zoomdb instance.
        """
        j = self.zoom_db.get_job()
        self.assertEqual(j.id, self.zoom_db._job_id)

    def test_add_config_guess(self):
        """
        Add a project configuration guess to the DB.
        """
        self.assertEqual(self.soup.dz2_configguess.count(), 0)
        self.zoom_db.add_config_guess(field="f",
                                      value="v",
                                      is_primary=True,
                                      basis="testing")
        self.assertEqual(self.soup.dz2_configguess.count(), 1)

    def test_get_project(self):
        """
        Get the project associated with the current zoomdb instance's job.
        """
        p = self.zoom_db.get_project()
        j = self.zoom_db.get_job()
        self.assertEqual(j.project_id, p.id)

    def test_modify_project(self):
        """
        Modify a project and save changes.
        """
        fake_hostname = "pants" + str(random.randint(1000, 9999))
        p = self.zoom_db.get_project()
        self.assertTrue(p.db_host is None)
        p.db_host = fake_hostname
        self.zoom_db.flush()

        p2 = self.soup.dz2_project.filter(self.soup.dz2_project.id == 2).one()
        self.assertEqual(p2.db_host, fake_hostname)

    def test_app_bundles(self):
        """
        Log a new AppBundle in the DB.
        """

        buns = self.zoom_db.get_all_bundles()
        self.assertEqual(len(buns), 0)

        bun_attrs = {
            "bundle_name": "some_bundle",
            "code_revision": "16b1fe9968368ba5346ebdcc53992171852c5949",
            }

        bun = self.zoom_db.add_bundle(**bun_attrs)
        self.assertEqual(bun.id, 1)

        buns = self.zoom_db.get_all_bundles()
        self.assertEqual(len(buns), 1)
        bun0 = buns[0]

        for k, v in bun_attrs.items():
            self.assertEqual(getattr(bun0, k), v)

    def test_long_commit_msg_truncation(self):
        long_msg = "x" * 5000
        bun = self.zoom_db.add_bundle(bundle_name="abundle",
                                      code_revision=long_msg)
        self.assertEqual(len(bun.code_revision), 255)

    def test_get_vhosts(self):
        """Test getting project virtual host names."""
        proj_id = taskconfig.PROJECT_SYSID_FORMAT % \
            self.zoom_db.get_project_id()
        expected = ["%s.djangozoom.net" % proj_id]

        self.assertEqual(self.zoom_db.get_project_virtual_hosts(), expected)
