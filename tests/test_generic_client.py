from unittest import TestCase
from potion.client import Client, Resource


class ClientTestCase(TestCase):

    def __init__(self):
        pass

    def test_simple_resolution(self):
        client = Client('http://example.com/schema')

        self.assertTrue(isinstance(client.Book, Resource))

        self.assertEqual('/book/offers', client.Book.offers.uri)
        self.assertEqual('GET', client.Book.offers.method)

        book_1 = client.Book.read(1)
        self.assertEqual('/book/1/is-new', book_1.is_new.uri)

