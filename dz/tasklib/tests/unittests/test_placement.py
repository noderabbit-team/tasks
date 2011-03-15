from dz.tasklib.tests.dztestcase import DZTestCase
from dz.tasklib import (placement,
                        taskconfig)


class PlacementTestCase(DZTestCase):

    def test_placement(self):
        """Test our simple placement function."""
        self.assertEqual(placement.placement("some_app_id"),
                         taskconfig.APPSERVERS)
