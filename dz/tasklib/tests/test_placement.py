from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib import (placement,
                        taskconfig)


class PlacementTestCase(DZTestCase):

    def test_placement(self):
        self.assertEqual(placement.placement("some_app_id"),
                         taskconfig.APPSERVERS)
