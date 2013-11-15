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


try:
    from hashlib import md5
except ImportError: # pragma: no coverage
    from md5 import md5

from mock import Mock
from twisted.trial import unittest
from twisted.test import proto_helpers

from octothorpe.ami import AMIProtocol
from octothorpe.base import ActionException, ProtocolError
from octothorpe.channel import Channel, STATE_DOWN
from octothorpe.test.test_base import disassembleMessage


"""Tests for octothorpe.ami"""


class AMIProtocolTestCase(unittest.TestCase):
    """Test case for the AMI protocol"""

    def _setUpProtocol(self, cls=AMIProtocol):
        """Set up the protocol"""

        self.protocol = cls()
        self.transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(self.transport)


    def setUp(self):
        self._setUpProtocol()


    def _startAndLoginMD5(self):
        """Helper to start the protocol and do most of an MD5 login"""

        self.protocol.started = True
        d = self.protocol.loginMD5('username', 'secret')

        fields = disassembleMessage(self.transport.value())
        self.transport.clear()
        self.assertEqual(fields['action'], 'Challenge')
        self.assertIn('actionid', fields)
        self.assertEqual(fields['authtype'], 'MD5')

        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + fields['actionid'] + '\r\n'
            'Challenge: foo\r\n'
            '\r\n'
        )

        fields = disassembleMessage(self.transport.value())
        self.assertEqual(fields['action'], 'Login')
        self.assertIn('actionid', fields)
        self.assertEqual(fields['authtype'], 'MD5')
        self.assertEqual(fields['username'], 'username')
        self.assertEqual(fields['key'], md5('foo' + 'secret').hexdigest())

        return d, fields

    def test_loginMD5(self):
        """Log in to the server using MD5 challenge-response"""

        d, fields = self._startAndLoginMD5()
        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + fields['actionid'] + '\r\n'
            '\r\n'
        )
        return d


    def test_loginMD5Failure(self):
        """Fail to log in to the server using MD5"""

        d, fields = self._startAndLoginMD5()
        self.protocol.dataReceived(
            'Response: Error\r\n'
            'ActionID: ' + fields['actionid'] + '\r\n'
            '\r\n'
        )
        self.assertFailure(d, ActionException)
        return d


    def test_channelClass(self):
        """Use of channelClass to spawn a custom class"""

        class TestChannel(Channel):
            pass

        class TestAMIProtocol(AMIProtocol):
            channelClass = TestChannel
            def newChannel(self, name, channel):
                assert isinstance(channel, TestChannel)

        self._setUpProtocol(TestAMIProtocol)
        self.protocol.started = True
        self.protocol.dataReceived(
            'Event: Newchannel\r\n'
            'Channel: Foo/201-0\r\n'
            'ChannelState: 0\r\n'
            'ChannelStateDesc: Down\r\n'
            '\r\n'
        )
        self.assertIn('Foo/201-0', self.protocol.channels)


    def test_newChannel(self):
        """New channel created"""

        self.protocol.started = True
        self.protocol.newChannel = Mock()
        self.protocol.dataReceived(
            'Event: Newchannel\r\n'
            'AccountCode: 123\r\n'
            'CallerIDName: Foo\r\n'
            'CallerIDNum: 201\r\n'
            'Channel: Foo/202-0\r\n'
            'ChannelState: 0\r\n'
            'ChannelStateDesc: Down\r\n'
            'Context: default\r\n'
            'Exten: \r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        self.protocol.newChannel.assert_called_once()
        name, args, kwargs = self.protocol.newChannel.mock_calls[0]
        channelName, channel = args
        self.assertEqual(channelName, 'Foo/202-0')
        self.assertEqual(channel.params,
            {
                'accountcode': '123',
                'calleridname': 'Foo',
                'calleridnum': '201',
                'channel': 'Foo/202-0',
                'channelstate': 0,
                'channelstatedesc': 'Down',
                'context': 'default',
                'exten': '',
                'uniqueid': '1234567890.0'
            }
        )
        self.assertEqual(channel.state, STATE_DOWN)
        self.assertIn('Foo/202-0', self.protocol.channels)
        assert self.protocol.channels['Foo/202-0'] is channel
        assert channel.protocol is self.protocol 


    def test_newChannel4(self):
        """New channel created with 1.4-era State parameter"""

        self.protocol.started = True
        self.protocol.newChannel = Mock()
        self.protocol.dataReceived(
            'Event: Newchannel\r\n'
            'Channel: Foo/202-0\r\n'
            'State: Down\r\n'
            'CallerIDNum: 202\r\n'
            'CallerIDName: Foo\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        self.protocol.newChannel.assert_called_once()
        name, args, kwards = self.protocol.newChannel.mock_calls[0]
        channelName, channel = args
        self.assertEqual(channelName, 'Foo/202-0')
        self.assertEqual(channel.params,
            {
                'channel': 'Foo/202-0',
                'channelstate': 0,
                'channelstatedesc': 'Down',
                'calleridname': 'Foo',
                'calleridnum': '202',
                'state': 'Down',
                'uniqueid': '1234567890.0'
            }
        )
        self.assertEqual(channel.state, STATE_DOWN)
        self.assertIn('Foo/202-0', self.protocol.channels)
        assert self.protocol.channels['Foo/202-0'] is channel
        assert channel.protocol is self.protocol


    def _startAndSpawnChannel(self):
        """Helper to start the protocol and spawn a channel"""

        self.protocol.started = True
        self.protocol.channels['Foo/202-0'] = channel = Channel(
            self.protocol,
            'Foo/202-0',
            {
                'accountcode': '123',
                'calleridname': 'Foo',
                'calleridnum': '201',
                'channel': 'Foo/202-0',
                'channelstate': '0',
                'channelstatedesc': 'Down',
                'context': 'default',
                'exten': '',
                'uniqueid': '1234567890.0'
            }
        )
        return channel


    def test_newState(self):
        """Channel state changed"""

        channel = self._startAndSpawnChannel()
        channel.newState = Mock()
        self.protocol.dataReceived(
            'Event: Newstate\r\n'
            'CallerIDName: \r\n'
            'CallerIDNum: 202\r\n'
            'Channel: Foo/202-0\r\n'
            'ChannelState: 6\r\n'
            'ChannelStateDesc: Up\r\n'
            'ConnectedLineName: \r\n'
            'ConnectedLineNum: \r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        channel.newState.assert_called_once_with(6, 'Up')
        self.assertEqual(channel.state, 6)
        self.assertEqual(channel.params['channelstate'], 6)
        self.assertEqual(channel.params['channelstatedesc'], 'Up')


    def test_newState4(self):
        """Channel state changed with Asterisk-1.4-era parameters"""

        channel = self._startAndSpawnChannel()
        channel.newState = Mock()
        self.protocol.dataReceived(
            'Event: Newstate\r\n'
            'Channel: Foo/202-0\r\n'
            'State: Ring\r\n'
            'CallerID: 202\r\n'
            'CallerIDName: \r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        channel.newState.assert_called_once_with(4, 'Ring')
        self.assertEqual(channel.state, 4)
        self.assertEqual(channel.params['channelstate'], 4)
        self.assertEqual(channel.params['channelstatedesc'], 'Ring')


    def test_newCallerId(self):
        """Channel caller ID changed"""

        channel = self._startAndSpawnChannel()
        channel.newCallerId = Mock()
        self.protocol.dataReceived(
            'Event: NewCallerid\r\n'
            'CallerIDName: John Doe\r\n'
            'CallerIDNum: 8885551212\r\n'
            'Channel: Foo/202-0\r\n'
            'CID-CallingPres: 0 (Presentation Allowed, Not Screened)\r\n'
            'Uniqueid: 123456789.0\r\n'
            '\r\n'
        )
        channel.newCallerId.assert_called_once_with('8885551212', 'John Doe')
        self.assertEqual(channel.params['calleridnum'], '8885551212')
        self.assertEqual(channel.params['calleridname'], 'John Doe')


    def test_variableSet(self):
        """Channel variable set"""

        channel = self._startAndSpawnChannel()
        channel.variableSet = Mock()
        self.protocol.dataReceived(
            'Event: VarSet\r\n'
            'Channel: Foo/202-0\r\n'
            'Variable: BAR\r\n'
            'Value: BAZ\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        channel.variableSet.assert_called_once_with('BAR', 'BAZ')
        self.assertIn('BAR', channel.variables)
        self.assertEqual(channel.variables['BAR'], 'BAZ')


    def test_hungUp(self):
        """Channel hung up"""

        channel = self._startAndSpawnChannel()
        channel.hungUp = Mock()
        self.protocol.dataReceived(
            'Event: Hangup\r\n'
            'AccountCode: 123\r\n'
            'CallerIDName: <unknown>\r\n'
            'CallerIDNum: 201\r\n'
            'Cause: 17\r\n'
            'Cause-Txt: User busy\r\n'
            'Channel: Foo/202-0\r\n'
            'ConnectedLineName: <unknown>\r\n'
            'ConnectedLineNum: <unknown>\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        channel.hungUp.assert_called_once_with(17, 'User busy')
        self.assertNotIn('Foo/202-0', self.protocol.channels)


    def test_renamed(self):
        """Channel was renamed"""

        channel = self._startAndSpawnChannel()
        channel.renamed = Mock()
        self.protocol.dataReceived(
            'Event: Rename\r\n'
            'Channel: Foo/202-0\r\n'
            'Newname: Bar/303-0\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        channel.renamed.assert_called_once_with('Foo/202-0', 'Bar/303-0')
        self.assertEqual(channel.name, 'Bar/303-0')
        self.assertNotIn('Foo/202-0', self.protocol.channels)
        assert self.protocol.channels['Bar/303-0'] is channel


    def test_renamedOldSchool(self):
        """Channel was renamed using an Oldname key"""

        channel = self._startAndSpawnChannel()
        channel.renamed = Mock()
        self.protocol.dataReceived(
            'Event: Rename\r\n'
            'Oldname: Foo/202-0\r\n'
            'Newname: Bar/303-0\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        channel.renamed.assert_called_once_with('Foo/202-0', 'Bar/303-0')
        self.assertEqual(channel.name, 'Bar/303-0')
        self.assertNotIn('Foo/202-0', self.protocol.channels)
        assert self.protocol.channels['Bar/303-0'] is channel


    def test_extensionEntered(self):
        """Channel enters a new context/extension/priority"""

        channel = self._startAndSpawnChannel()
        channel.extensionEntered = Mock()
        self.protocol.dataReceived(
            'Event: Newexten\r\n'
            'Application: Playback\r\n'
            'AppData: hello-world\r\n'
            'Channel: Foo/202-0\r\n'
            'Context: default\r\n'
            'Extension: 202\r\n'
            'Priority: 3\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        self.assertEqual(len(channel.extensionEntered.mock_calls), 1)
        name, args, kwargs = channel.extensionEntered.mock_calls[0]
        self.assertEqual(args, ('default', '202', 3, 'Playback', 'hello-world'))
        firstArgs = args
        self.assertEqual(channel.extensions, [firstArgs])
        self.protocol.dataReceived(
            'Event: Newexten\r\n'
            'Application: Dial\r\n'
            'AppData: Bar/303\r\n'
            'Channel: Foo/202-0\r\n'
            'Context: default\r\n'
            'Extension: 202\r\n'
            'Priority: 4\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        self.assertEqual(len(channel.extensionEntered.mock_calls), 2)
        name, args, kwargs = channel.extensionEntered.mock_calls[1]
        self.assertEqual(args, ('default', '202', 4, 'Dial', 'Bar/303'))
        self.assertEqual(channel.extensions, [firstArgs, args])


    def _spawnAnotherChannel(self, name='Bar/303-0'):
        channel = Channel(self.protocol, name,
            {
                'channelstate': 0,
                'channelstatedesc': 'Down',
            }
        )
        self.protocol.channels[name] = channel
        return channel


    def test_linked(self):
        """Channel is linked to another channel"""

        channel = self._startAndSpawnChannel()
        channel.linked = Mock()
        channel2 = self._spawnAnotherChannel()
        self.assertEqual(channel.linkedTo, None)
        self.assertEqual(channel2.linkedTo, None)
        self.protocol.dataReceived(
            'Event: Link\r\n'
            'Channel1: Foo/202-0\r\n'
            'Channel2: Bar/303-0\r\n'
            'Uniqueid1: 1234567890.0\r\n'
            'Uniqueid2: 0987654321.0\r\n'
            'CallerID1: 202\r\n'
            'CallerID2: 303\r\n'
            '\r\n'
        )
        channel.linked.assert_called_once_with(channel2)
        self.assertEqual(channel.linkedTo, channel2)
        self.assertEqual(channel2.linkedTo, channel)
        self.assertRaises(
            ProtocolError,
            self.protocol.dataReceived,
            'Event: Link\r\n'
            'Channel1: Foo/202-0\r\n'
            'Channel2: Bar/303-0\r\n'
            'Uniqueid1: 1234567890.0\r\n'
            'Uniqueid2: 0987654321.0\r\n'
            'CallerID1: 202\r\n'
            'CallerID2: 303\r\n'
            '\r\n'
        )


    def test_unlinked(self):
        """Channel is unlinked from another channel"""

        channel = self._startAndSpawnChannel()
        channel.unlinked = Mock()
        channel2 = self._spawnAnotherChannel()
        channel.linkedTo = channel2
        channel2.linkedTo = channel
        channel3 = self._spawnAnotherChannel('Baz/404-0')
        self.assertRaises(
            ProtocolError,
            self.protocol.dataReceived,
            'Event: Unlink\r\n'
            'Channel1: Foo/202-0\r\n'
            'Channel2: Baz/404-0\r\n'
            'Uniqueid1: 1234567890.0\r\n'
            'Uniqueid2: 0987654321.0\r\n'
            'CallerID1: 202\r\n'
            'CallerID2: 303\r\n'
            '\r\n'
        )
        self.protocol.dataReceived(
            'Event: Unlink\r\n'
            'Channel1: Foo/202-0\r\n'
            'Channel2: Bar/303-0\r\n'
            'Uniqueid1: 1234567890.0\r\n'
            'Uniqueid2: 0987654321.0\r\n'
            'CallerID1: 202\r\n'
            'CallerID2: 303\r\n'
            '\r\n'
        )
        channel.unlinked.assert_called_once_with(channel2)
        self.assertEqual(channel.linkedTo, None)
        self.assertEqual(channel2.linkedTo, None)
        self.assertRaises(
            ProtocolError,
            self.protocol.dataReceived,
            'Event: Unlink\r\n'
            'Channel1: Foo/202-0\r\n'
            'Channel2: Bar/303-0\r\n'
            'Uniqueid1: 1234567890.0\r\n'
            'Uniqueid2: 0987654321.0\r\n'
            'CallerID1: 202\r\n'
            'CallerID2: 303\r\n'
            '\r\n'
        )


    def test_dial(self):
        """Channel dial"""

        channel = self._startAndSpawnChannel()
        channel.dialBegin = Mock()
        channel.dialEnd = Mock()
        self.assertRaises(
            ProtocolError,
            self.protocol.dataReceived,
            'Event: Dial\r\n'
            'DialStatus: <unknown>\r\n'
            'SubEvent: Foo\r\n'
            'Channel: Foo/202-0\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        self.protocol.dataReceived(
            'Event: Dial\r\n'
            'SubEvent: Begin\r\n'
            'CallerIDName: Foo\r\n'
            'CallerIDNum: 202\r\n'
            'Channel: Foo/202-0\r\n'
            'ConnectedLineName: <unknown>\r\n'
            'ConnectedLineNum: <unknown>\r\n'
            'Destination: Bar/303-0\r\n'
            'DestUniqueid: 0987654321.0\r\n'
            'DialString: 303\r\n'
            'Uniqueid: 1234567890.0\r\n'
            '\r\n'
        )
        channel.dialBegin.assert_called_once_with('Bar/303-0', '303')
        self.protocol.dataReceived(
            'Event: Dial\r\n'
            'SubEvent: End\r\n'
            'DialStatus: ANSWER\r\n'
            'Channel: Foo/202-0\r\n'
            'Uniqueid: 123456789.0\r\n'
            '\r\n'
        )
        channel.dialEnd.assert_called_once_with('ANSWER')


    def test_dial4(self):
        """Channel dial from Asterisk 1.4"""

        channel = self._startAndSpawnChannel()
        channel.dialBegin = Mock()
        channel.dialEnd = Mock()
        self.protocol.dataReceived(
            'Event: Dial\r\n'
            'Source: Foo/202-0\r\n'
            'Destination: Bar/303-0\r\n'
            'CallerID: 202\r\n'
            'CallerIDName: Foo\r\n'
            'SrcUniqueID: 1234567890.0\r\n'
            'DestUniqueID: 0987654321.0\r\n'
            '\r\n'
        )
        channel.dialBegin.assert_called_once_with('Bar/303-0', None)


    def test_hangup(self):
        """Channel hangup"""

        channel = self._startAndSpawnChannel()
        channel.hungUp = Mock()
        self.protocol.dataReceived(
            'Event: Hangup\r\n'
            'AccountCode: 123\r\n'
            'Cause: 16\r\n'
            'Cause-txt: Normal Clearing\r\n'
            'Channel: Foo/202-0\r\n'
            'CallerIDNum: 202\r\n'
            'CallerIDName: Foo\r\n'
            'ConnectedLineNum: 303\r\n'
            'ConnectedLineName: Bar\r\n'
            '\r\n'
        )
        channel.hungUp.assert_called_once_with(16, 'Normal Clearing')
        self.assertNotIn('Foo/202-0', self.protocol.channels)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
