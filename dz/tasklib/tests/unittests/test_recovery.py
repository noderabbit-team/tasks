from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib.tests.stub_zoomdb import StubZoomDB

from dz.tasklib import recovery


class RecoverTestCase(DZTestCase):
    def setUp(self):
        self.zoomdb = StubZoomDB()

    def test_recover_appserver(self):
        failed_appserver_ips = ["localhost"]
        recovery.recover_appserver(self.zoomdb, failed_appserver_ips)

    # def test_recovery_result(self):
    #     # add a couple of workers
    #     instance_id, ip = "i-b0rk3d", "123.123.123.123"
    #     ip2 = "123.1.2.3"
    #     w1 = self.zoomdb.add_worker(1, instance_id, ip, "10256")
    #     w2 = self.zoomdb.add_worker(2, instance_id, ip, "10257")
    #     w3 = self.zoomdb.add_worker(3, instance_id, ip2, "10257")

    #     import ipdb; ipdb.set_trace()
        
    #     result = recovery.recover_appserver(self.zoomdb, ip)
    #     self.assertEqual(len(result), 2)
    #     self.assertTrue(w1 in result)
    #     self.assertTrue(w2 in result)
    #     self.assertTrue(w3 not in result)
