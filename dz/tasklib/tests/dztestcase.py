from mocker import MockerTestCase

_missing = object()


class DZTestCase(MockerTestCase):
    """
    Base TestCase class for DjangoZoom tests. Put reusable test stuff in here.
    """

    def patch(self, ob, attr, value):
        """Patch a specific object attribute for the duration of a test."""
        old_value = getattr(ob, attr, _missing)
        setattr(ob, attr, value)

        def restore():
            if old_value is _missing:
                delattr(ob, attr)
            else:
                setattr(ob, attr, old_value)

        self.addCleanup(restore)
