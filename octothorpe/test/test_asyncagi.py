# Copyright (c) 2013 Matt Behrens <matt@zigg.com>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.


import urllib

from mock import Mock
from twisted.trial import unittest
from twisted.test import proto_helpers

from octothorpe.asyncagi import AsyncAGIProtocol, AsyncAGIChannel
from octothorpe.test.test_base import disassembleMessage


"""Tests for octothorpe.ami"""


class AsyncAGIProtocolTestCase(unittest.TestCase):
    """Test case for the AsyncAGI protocol"""

    def setUp(self):
        self.protocol = AsyncAGIProtocol()
        self.transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(self.transport)
        self.protocol.started = True


    def _spawnChannel(self, name='Foo/202-0'):
        self.protocol.channels[name] = channel = AsyncAGIChannel(
            self.protocol,
            name,
            {
                'calleridname': 'Foo',
                'calleridnum': '202',
                'channel': name,
                'channelstate': '0',
                'channelstatedesc': 'Down',
            }
        )
        return channel


    def test_asyncAGIStart(self):
        """Respond to an AsyncAGI Start event"""

        channel = self._spawnChannel()
        started = channel.asyncAGIStarted = Mock()
        env = urllib.quote(
            'agi_request: async\n'
            'agi_channel: Foo/202-0\n'
            'agi_context: default\n'
            'agi_extension: 400\n'
            'agi_priority: 1\n'
            '\n'
        )
        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'Channel: Foo/202-0\r\n'
            'Env: ' + env + '\r\n'
            'Subevent: Start\r\n'
            '\r\n'
        )
        started.assert_called_once_with(
            'default', '400', 1, {
                'agi_request': 'async',
                'agi_channel': 'Foo/202-0',
                'agi_context': 'default',
                'agi_extension': '400',
                'agi_priority': '1',
            }
        )


    def test_queueAGI(self):
        """Queue an AGI command"""

        channel = self._spawnChannel()
        d = channel.queueAGI('EXEC Playback hello-world')

        message = disassembleMessage(self.transport.value())
        self.assertEqual(message['action'], 'AGI')
        self.assertIn('actionid', message)
        self.assertEqual(message['command'], 'EXEC Playback hello-world')
        self.assertIn('commandid', message)

        cbSuccess = Mock()
        d.addCallback(cbSuccess)
        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            '\r\n'
            'Event: AsyncAGI\r\n'
            'SubEvent: Exec\r\n'
            'Channel: Foo/202-0\r\n'
            'CommandID: ' + message['commandid'] + '\r\n'
            'Result: 200%20result%3D0%0A\r\n'
            '\r\n'
        )
        cbSuccess.assert_called_once_with(0)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
