import unittest
import htpasswd


class TestHtpasswd(unittest.TestCase):

    def test_create_htpasswd_secret(self):
        expected = 'therealme:$apr1$SHWthwzC$E0vrTpcg82VoNUDftOq8r.'
        actual = htpasswd.create_secret('therealme', 'tothedemo')
        self.assertEqual(expected, actual, "htpasswd credentials generated do not match expectation")