import unittest
import asyncio
import os

from ._testutil import BaseTest, run_until_complete
from aioredis import create_connection, ReplyError, ProtocolError


class ConnectionTest(BaseTest):

    @run_until_complete
    def test_connect_tcp(self):
        conn = yield from create_connection(
            ('localhost', self.redis_port), loop=self.loop)
        self.assertEqual(conn.db, 0)
        self.assertEqual(str(conn), '<RedisConnection [db:0]>')

        conn = yield from create_connection(
            ['localhost', self.redis_port], loop=self.loop)
        self.assertEqual(conn.db, 0)
        self.assertEqual(str(conn), '<RedisConnection [db:0]>')

    @unittest.skipIf(not os.environ.get('REDIS_SOCKET'), "no redis socket")
    @run_until_complete
    def test_connect_unixsocket(self):
        conn = yield from create_connection(
            self.redis_socket, db=0, loop=self.loop)
        self.assertEqual(conn.db, 0)
        self.assertEqual(str(conn), '<RedisConnection [db:0]>')

    def test_global_loop(self):
        asyncio.set_event_loop(self.loop)

        conn = self.loop.run_until_complete(create_connection(
            ('localhost', self.redis_port), db=0))
        self.assertEqual(conn.db, 0)
        self.assertIs(conn._loop, self.loop)

    @run_until_complete
    def test_select_db(self):
        address = ('localhost', self.redis_port)
        conn = yield from create_connection(address, loop=self.loop)
        self.assertEqual(conn.db, 0)

        with self.assertRaises(ValueError):
            yield from create_connection(address, db=-1, loop=self.loop)
        with self.assertRaises(TypeError):
            yield from create_connection(address, db=1.0, loop=self.loop)
        with self.assertRaises(TypeError):
            yield from create_connection(
                address, db='bad value', loop=self.loop)
        with self.assertRaises(TypeError):
            conn = yield from create_connection(
                address, db=None, loop=self.loop)
            yield from conn.select(None)
        with self.assertRaises(ReplyError):
            yield from create_connection(
                address, db=100000, loop=self.loop)

        yield from conn.select(1)
        self.assertEqual(conn.db, 1)
        yield from conn.select(2)
        self.assertEqual(conn.db, 2)
        yield from conn.execute('select', 0)
        self.assertEqual(conn.db, 0)

    @run_until_complete
    def test_protocol_error(self):
        loop = self.loop
        conn = yield from create_connection(
            ('localhost', self.redis_port), loop=loop)

        reader = conn._reader

        with self.assertRaises(ProtocolError):
            reader.feed_data(b'not good redis protocol response')
            yield from conn.select(1)

        self.assertEqual(conn._waiters.qsize(), 0)

    def test_close_connection__tcp(self):
        loop = self.loop
        conn = loop.run_until_complete(create_connection(
            ('localhost', self.redis_port), loop=loop))
        conn.close()
        with self.assertRaises(AttributeError):     # FIXME
            loop.run_until_complete(conn.select(1))

        conn = loop.run_until_complete(create_connection(
            ('localhost', self.redis_port), loop=loop))
        with self.assertRaises(AttributeError):     # FIXME
            coro = conn.select(1)
            conn.close()
            loop.run_until_complete(coro)

    @unittest.skipIf(not os.environ.get('REDIS_SOCKET'), "no redis socket")
    @run_until_complete
    def test_close_connection__socket(self):
        conn = yield from create_connection(
            self.redis_socket, loop=self.loop)
        conn.close()
        with self.assertRaises(AttributeError):     # FIXME
            yield from conn.select(1)

    @run_until_complete
    def test_auth(self):
        conn = yield from create_connection(
            ('localhost', self.redis_port), loop=self.loop)

        res = yield from conn.execute('CONFIG', 'SET', 'requirepass', 'pass')
        self.assertEqual(res, b'OK')

        conn2 = yield from create_connection(
            ('localhost', self.redis_port), loop=self.loop)

        with self.assertRaises(ReplyError):
            yield from conn2.select(1)

        res = yield from conn2.auth('pass')
        self.assertEqual(res, True)
        res = yield from conn2.select(1)
        self.assertTrue(res)

        res = yield from conn2.execute('CONFIG', 'SET', 'requirepass', '')
        self.assertEqual(res, b'OK')