# Copyright (c) 2013, 2014 Matt Behrens <matt@zigg.com>
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


from urllib import quote

from mock import Mock
from twisted.trial import unittest
from twisted.test import proto_helpers

from octothorpe.asyncagi import AGIException, AsyncAGIProtocol, AsyncAGIChannel
from octothorpe.asyncagi import ResultException, UnknownCommandException
from octothorpe.base import ProtocolError
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


    def test_AGIExceptionRepr(self):
        """repr() of an AGIException"""

        self.assertEqual(
            repr(AGIException(500, 'foobar')),
            "<AGIException code=500 message='foobar'>"
        )


    def test_ResultExceptionRepr(self):
        """repr() of a PlaybackException"""

        self.assertEqual(
            repr(ResultException(64)),
            '<ResultException result=64>'
        )


    def test_asyncAGIStart(self):
        """Respond to an AsyncAGI Start event"""

        channel = self._spawnChannel()
        started = channel.asyncAGIStarted = Mock()
        env = quote(
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


    def test_originateWithCallerId(self):
        """Originate an AsyncAGI call with caller ID
        
        Only tests the Caller ID kwarg.  The remainder of the originate
        functionality is tested by test_originateAsyncAGI.
        
        """
        channel = self._spawnChannel()
        d = self.protocol.originateAsyncAGI('Foo/202', callerId='Bar <303>')

        message = disassembleMessage(self.transport.value())
        self.assertEqual(message['action'], 'Originate')
        self.assertIn('actionid', message)
        self.assertEqual(message['application'], 'AGI')
        self.assertEqual(message['data'], 'agi:async')
        self.assertEqual(message['async'], 'true')
        self.assertEqual(message['callerid'], 'Bar <303>')


    def _setUpOriginateAsyncAGI(self):
        channel = self._spawnChannel()
        d = self.protocol.originateAsyncAGI('Foo/202')

        message = disassembleMessage(self.transport.value())
        self.assertEqual(message['action'], 'Originate')
        self.assertIn('actionid', message)
        self.assertEqual(message['application'], 'AGI')
        self.assertEqual(message['data'], 'agi:async')
        self.assertEqual(message['async'], 'true')

        varName, octoId = message['variable'].split('=')
        self.assertEqual(varName, 'AsyncOrigId')

        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            'Message: Originate successfully queued\r\n'
            '\r\n'
            'Event: VarSet\r\n'
            'Channel: Foo/202-0\r\n'
            'Variable: AsyncOrigId\r\n'
            'Value: ' + octoId + '\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )

        return d, channel, message


    def test_originateAsyncAGIFail(self):
        """Fail to originate an AsyncAGI call"""

        d, channel, message = self._setUpOriginateAsyncAGI()
        origFailed = Mock()
        d.addErrback(origFailed)

        self.protocol.dataReceived(
            'Event: OriginateResponse\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            'Channel: Foo/202\r\n'
            'Reason: 5\r\n'
            'Response: Failure\r\n'
            'Uniqueid: <null>\r\n'
            '\r\n'
        )

        self.assertEqual(len(origFailed.mock_calls), 1)


    def test_originateAsyncAGI(self):
        """Originate an AsyncAGI call, calling back with channel"""

        d, channel, message = self._setUpOriginateAsyncAGI()
        originated = Mock()
        d.addCallback(originated)

        self.protocol.dataReceived(
            'Event: OriginateResponse\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            'Channel: Foo/202-0\r\n'
            'Response: Success\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        self.assertEqual(len(originated.mock_calls), 0)

        env = quote(
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
        originated.assert_called_once_with((channel, {
            'agi_request': 'async',
            'agi_channel': 'Foo/202-0',
            'agi_context': 'default',
            'agi_extension': '400',
            'agi_priority': '1',
        }))


    def test_AGI(self):
        """Successfully run an AGI command"""

        channel = self._spawnChannel()
        d = channel.sendAGI('EXEC Playback hello-world')

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
        )
        self.assertEqual(len(cbSuccess.mock_calls), 0)

        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'SubEvent: Exec\r\n'
            'Channel: Foo/202-0\r\n'
            'CommandID: ' + message['commandid'] + '\r\n'
            'Result: ' + quote('200 result=0 foo=bar\n') + '\r\n'
            '\r\n'
        )
        cbSuccess.assert_called_once_with((0, {'foo': 'bar'}))


    def test_AGIInvalid(self):
        """Fail to run an invalid AGI command"""

        channel = self._spawnChannel()
        d = channel.sendAGI('FOO')

        message = disassembleMessage(self.transport.value())
        self.assertEqual(message['action'], 'AGI')
        self.assertIn('actionid', message)
        self.assertEqual(message['command'], 'FOO')
        self.assertIn('commandid', message)

        cbSuccess = Mock()
        d.addCallback(cbSuccess)

        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            '\r\n'
        )
        self.assertEqual(len(cbSuccess.mock_calls), 0)

        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'SubEvent: Exec\r\n'
            'Channel: Foo/202-0\r\n'
            'CommandID: ' + message['commandid'] + '\r\n'
            'Result: ' + quote('510 Invalid or unknown command\n') + '\r\n'
            '\r\n'
        )
        self.assertEqual(len(cbSuccess.mock_calls), 0)
        self.assertFailure(d, AGIException)
        return d


    def test_unknownCommandId(self):
        """Connection is not dropped on an unknown command"""

        self._spawnChannel()
        lose = self.transport.loseConnection = Mock()
        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'SubEvent: Exec\r\n'
            'Channel: Foo/202-0\r\n'
            'CommandID: bar\r\n'
            'Result: ' + quote('200 result=0\n') + '\r\n'
            '\r\n'
        )
        self.assertFalse(lose.called)
        self.assertEqual(len(self.flushLoggedErrors(ProtocolError)), 0)


    def test_AGIExecPlayback(self):
        """Successfully execute the Playback command"""

        channel = self._spawnChannel()
        d = channel.sendAGIExecPlayback('hello-world')

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
        )
        self.assertEqual(len(cbSuccess.mock_calls), 0)

        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'SubEvent: Exec\r\n'
            'Channel: Foo/202-0\r\n'
            'CommandID: ' + message['commandid'] + '\r\n'
            'Result: ' + quote('200 result=0\n') + '\r\n'
            '\r\n'
        )
        cbSuccess.assert_called_once_with(0)


    def test_AGIExecPlaybackFailed(self):
        """Fail to execute the Playback command"""

        channel = self._spawnChannel()
        d = channel.sendAGIExecPlayback('hello-world')

        message = disassembleMessage(self.transport.value())
        self.assertEqual(message['action'], 'AGI')
        self.assertIn('actionid', message)
        self.assertEqual(message['command'], 'EXEC Playback hello-world')
        self.assertIn('commandid', message)

        playbackFailed = Mock()
        d.addErrback(playbackFailed)

        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            '\r\n'
        )
        self.assertEqual(len(playbackFailed.mock_calls), 0)

        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'SubEvent: Exec\r\n'
            'Channel: Foo/202-0\r\n'
            'CommandID: ' + message['commandid'] + '\r\n'
            'Result: '
            '' + quote('200 result=-1\n') + ''
            '\r\n'
            '\r\n'
        )

        self.assertEqual(len(playbackFailed.mock_calls), 1)


    def test_AGIExecPlaybackBackground(self):
        """Successfully execute Playback in background mode"""

        channel = self._spawnChannel()
        d = channel.sendAGIExecPlayback('hello-world', background=True)

        message = disassembleMessage(self.transport.value())
        self.assertEqual(message['action'], 'AGI')
        self.assertIn('actionid', message)
        self.assertEqual(message['command'], 'EXEC Background hello-world')
        self.assertIn('commandid', message)

        cbSuccess = Mock()
        d.addCallback(cbSuccess)

        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            '\r\n'
        )
        self.assertEqual(len(cbSuccess.mock_calls), 0)

        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'SubEvent: Exec\r\n'
            'Channel: Foo/202-0\r\n'
            'CommandID: ' + message['commandid'] + '\r\n'
            'Result: ' + quote('200 result=48\n') + '\r\n'
            '\r\n'
        )
        cbSuccess.assert_called_once_with(48)


    def test_AGIHangup(self):
        """Successfully send an AGI hangup"""

        channel = self._spawnChannel()
        d = channel.sendAGIHangup()

        message = disassembleMessage(self.transport.value())
        self.assertEqual(message['action'], 'AGI')
        self.assertIn('actionid', message)
        self.assertEqual(message['command'], 'HANGUP')
        self.assertIn('commandid', message)

        cbSuccess = Mock()
        d.addCallback(cbSuccess)

        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            '\r\n'
        )
        self.assertEqual(len(cbSuccess.mock_calls), 0)

        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'SubEvent: Exec\r\n'
            'Channel: Foo/202-0\r\n'
            'CommandID: ' + message['commandid'] + '\r\n'
            'Result: ' + quote('200 result=1\n') + '\r\n'
            '\r\n'
        )
        cbSuccess.assert_called_once_with(1)


    def test_AGIHangupFailed(self):
        """Fail to hang up the channel"""

        channel = self._spawnChannel()
        d = channel.sendAGIHangup()

        message = disassembleMessage(self.transport.value())
        self.assertEqual(message['action'], 'AGI')
        self.assertIn('actionid', message)
        self.assertEqual(message['command'], 'HANGUP')
        self.assertIn('commandid', message)

        hangupFailed = Mock()
        d.addErrback(hangupFailed)

        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + message['actionid'] + '\r\n'
            '\r\n'
        )
        self.assertEqual(len(hangupFailed.mock_calls), 0)

        self.protocol.dataReceived(
            'Event: AsyncAGI\r\n'
            'SubEvent: Exec\r\n'
            'Channel: Foo/202-0\r\n'
            'CommandID: ' + message['commandid'] + '\r\n'
            'Result: '
            '' + quote('200 result=0\n') + ''
            '\r\n'
            '\r\n'
        )
        self.assertEqual(len(hangupFailed.mock_calls), 1)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
