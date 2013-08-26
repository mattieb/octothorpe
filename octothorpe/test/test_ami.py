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


from hashlib import md5

from mock import Mock
from twisted.python import log
from twisted.trial import unittest
from twisted.test import proto_helpers

from octothorpe.ami import BaseAMIProtocol, AMIProtocol, Channel
from octothorpe.ami import ActionException, ProtocolError


"""Tests for octothorpe.ami"""

def disassembleMessage(data):
    """Disassemble a message into fields"""

    lines = data.split('\r\n')
    assert lines[-2:] == ['', '']
    fields = {}
    for line in lines[:-2]:
        key, value = line.split(': ', 2)
        fields[key.lower()] = value
    return fields


class DisassembleMessageTestCase(unittest.TestCase):
    """Test the disassembleMessage helper.
    
    Yes.  I'm testing my tests.
    
    """
    def test_goodMessage(self):
        """Disassemble a good message"""

        data = (
            'Foo: Bar\r\n'
            'Baz: Quux\r\n'
            '\r\n'
        )
        fields = {'foo': 'Bar', 'baz': 'Quux'}
        self.assertEqual(disassembleMessage(data), fields)


    def test_unterminatedMessage(self):
        """Fail to disassemble an unterminated message"""

        data = (
            'Foo: Bar\r\n'
            'Baz: Quux\r\n'
        )
        self.assertRaises(AssertionError, disassembleMessage, data)


    def test_invalidMessage(self):
        """Fail to disassemble an invalid message"""

        data = (
            'Foo: Bar\r\n'
            'Baz; Quux\r\n'
            '\r\n'
        )
        self.assertRaises(ValueError, disassembleMessage, data)


class BaseAMIProtocolTestCase(unittest.TestCase):
    """Test case for the base AMI protocol"""

    def setUp(self):
        self.protocol = BaseAMIProtocol()
        self.transport = proto_helpers.StringTransport()
        self.protocol.makeConnection(self.transport)


    def test_start(self):
        """Protocol starts when it receives a good banner"""

        self.assertFalse(self.protocol.started)
        self.protocol.dataReceived('Asterisk Call Manager/1.3\r\n')
        self.assertTrue(self.protocol.started)


    def test_badBanner(self):
        """ProtocolError is raised for a bad banner"""

        self.assertFalse(self.protocol.started)
        self.assertRaises(
            ProtocolError, self.protocol.dataReceived,
            '220 i.aint.no.asterisk ESMTP Foo\r\n'
        )
        self.assertFalse(self.protocol.started)


    def test_eventReceived(self):
        """Receive an event"""

        self.protocol.event_Foo = Mock()
        self.protocol.started = True
        self.protocol.dataReceived(
            'Event: Foo\r\n'
            'Key: Value\r\n'
            'Key2: Value2\r\n'
            '\r\n'
        )
        self.protocol.event_Foo.assert_called_once_with(
            {'key': 'Value', 'key2': 'Value2'}
        )


    def test_unknownActionID(self):
        """Receive a response to an unknown action"""

        self.protocol.started = True
        self.assertRaises(
            ProtocolError, self.protocol.dataReceived,
            'Response: Success\r\nActionID: Foo\r\n\r\n'
        )


    def _startAndSendAction(self):
        """Helper to start the protocol and send an action"""

        self.protocol.started = True
        d = self.protocol.sendAction(
            'Bar',
            {'key': 'Value', 'key2': 'Value2'}
        )

        fields = disassembleMessage(self.transport.value())
        self.assertEqual(fields['action'], 'Bar')
        self.assertIn('actionid', fields)
        self.assertEqual(fields['key'], 'Value')
        self.assertEqual(fields['key2'], 'Value2')

        return d, fields['actionid']

    def test_actionSuccess(self):
        """Send an action and get a success response"""

        d, actionid = self._startAndSendAction()
        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + actionid + '\r\n'
            'Key3: Value3\r\n'
            '\r\n'
        )
        d.addCallback(self.assertEqual, ({'key3': 'Value3'}, None))
        return d


    def test_actionError(self):
        """Send an action and get an error response"""

        d, actionid = self._startAndSendAction()
        self.protocol.dataReceived(
            'Response: Error\r\n'
            'ActionID: ' + actionid + '\r\n'
            '\r\n'
        )
        self.assertFailure(d, ActionException)
        return d


    def test_actionFollows(self):
        """Send a command action that will return a body"""

        d, actionid = self._startAndSendAction()
        self.protocol.dataReceived(
            'Response: Follows\r\n'
            'ActionID: ' + actionid + '\r\n'
            'foo bar\nbaz quux\n--END COMMAND--\r\n'
            '\r\n'
        )
        d.addCallback(self.assertEqual, ({}, 'foo bar\nbaz quux\n'))
        return d


    def test_actionBodyOnSuccessIsError(self):
        """ProtocolError for a Success response with a body"""

        d, actionid = self._startAndSendAction()
        self.assertRaises(
            ProtocolError, self.protocol.dataReceived,
            'Response: Success\r\n'
            'ActionID: ' + actionid + '\r\n'
            'foo bar\nbaz quux\n--END COMMAND--\r\n'
            '\r\n'
        )
   

    def test_actionBodyOnErrorIsError(self):
        """ProtocolError for a Success response with a body"""

        d, actionid = self._startAndSendAction()
        self.assertRaises(
            ProtocolError, self.protocol.dataReceived,
            'Response: Error\r\n'
            'ActionID: ' + actionid + '\r\n'
            'foo bar\nbaz quux\n--END COMMAND--\r\n'
            '\r\n'
        )


    def test_actionNoBodyOnFollowsIsError(self):
        """ProtocolError for a Success response with a body"""

        d, actionid = self._startAndSendAction()
        self.assertRaises(
            ProtocolError, self.protocol.dataReceived,
            'Response: Follows\r\n'
            'ActionID: ' + actionid + '\r\n'
            '\r\n'
        )


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
        name, args, kwargs = self.protocol.newChannel.mock_calls[0]
        self.assertEqual(args[0], 'Foo/202-0')
        self.assertEqual(
            args[1].params,
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
        self.assertIn('Foo/202-0', self.protocol.channels)
        self.assertIs(self.protocol.channels['Foo/202-0'], args[1])
        self.assertIs(args[1].protocol, self.protocol)


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
        name, args, kwargs = channel.variableSet.mock_calls[0]
        self.assertEqual(args, ('BAR', 'BAZ'))
        self.assertIn('BAR', channel.variables)
        self.assertEqual(channel.variables['BAR'], 'BAZ')


    def test_hangup(self):
        """Channel hung up"""

        channel = self._startAndSpawnChannel()
        channel.hangup = Mock()
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
        name, args, kwargs = channel.hangup.mock_calls[0]
        self.assertEqual(args, (17, 'User busy'))
        self.assertNotIn('Foo/202-0', self.protocol.channels)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
