from django.test import TestCase as TC

from testcube.core.models import *


class ModelsTestCase(TC):
    def setUp(self):
        Configuration.objects.create(key='test', value='unit')

    def test_get_set_config(self):
        assert Configuration.get('test') == 'unit'
        assert Configuration.get('nothing') is None
        assert Configuration.get('bad', default=123) == 123

        cfg = Configuration.objects.get(key='test')
        assert '{}'.format(cfg) == 'test'
