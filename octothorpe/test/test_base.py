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


from mock import Mock
from twisted.trial import unittest
from twisted.test import proto_helpers

from octothorpe.base import BaseAMIProtocol, ActionException, ProtocolError


"""Tests for octothorpe.base"""


def disassembleMessage(data):
    """Disassemble a message into fields"""

    lines = data.split('\r\n')
    if lines[-2:] != ['', '']:
        raise ValueError('unterminated message (%r)' % (data,))
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
        self.assertRaises(ValueError, disassembleMessage, data)


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
        """Connection is dropped on a bad banner"""

        lose = self.transport.loseConnection = Mock()
        self.assertFalse(self.protocol.started)
        self.protocol.dataReceived('220 i.aint.no.asterisk ESMTP Foo\r\n')
        self.assertTrue(lose.called)
        self.assertFalse(self.protocol.started)
        self.assertEqual(len(self.flushLoggedErrors(ProtocolError)), 1)


    def test_badMessage(self):
        """Connection is dropped on a bad message"""
        
        self.protocol.started = True
        lose = self.transport.loseConnection = Mock()
        self.protocol.dataReceived(
            'Foo: Bar\r\n'
            'Baz: Quux\r\n'
            '\r\n'
        )
        self.assertTrue(lose.called)
        self.assertEqual(len(self.flushLoggedErrors(ProtocolError)), 1)


    def test_eventReceived(self):
        """Receive an event"""

        self.protocol.event_foo = Mock()
        self.protocol.started = True
        self.protocol.dataReceived(
            'Event: Foo\r\n'
            'Key: Value\r\n'
            'Key2: Value2\r\n'
            '\r\n'
        )
        self.protocol.event_foo.assert_called_once_with(
            {'key': 'Value', 'key2': 'Value2'}
        )


    def test_unknownActionID(self):
        """Connection is not dropped on an unknown action"""

        self.protocol.started = True
        lose = self.transport.loseConnection = Mock()
        self.protocol.dataReceived(
            'Response: Success\r\nActionID: Foo\r\n\r\n'
        )
        self.assertFalse(lose.called)
        self.assertEqual(len(self.flushLoggedErrors(ProtocolError)), 0)


    def test_sendOwnActionID(self):
        """Send action with our own ActionID"""

        self.protocol.started = True
        d = self.protocol.sendAction(
            'Foo',
            {'key': 'Value', 'actionid': 'bar-baz-quux'}
        )

        fields = disassembleMessage(self.transport.value())
        self.assertEqual(fields['action'], 'Foo')
        self.assertEqual(fields['key'], 'Value')
        self.assertEqual(fields['actionid'], 'bar-baz-quux')


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
        """Connection is dropped on a Follows response with a body"""

        d, actionid = self._startAndSendAction()
        lose = self.transport.loseConnection = Mock()
        self.protocol.dataReceived(
            'Response: Success\r\n'
            'ActionID: ' + actionid + '\r\n'
            'foo bar\nbaz quux\n--END COMMAND--\r\n'
            '\r\n'
        )
        self.assertTrue(lose.called)
        self.assertEqual(len(self.flushLoggedErrors(ProtocolError)), 1)


    def test_actionBodyOnErrorIsError(self):
        """Connection is dropped on an Error response with a body"""

        d, actionid = self._startAndSendAction()
        lose = self.transport.loseConnection = Mock()
        self.protocol.dataReceived(
            'Response: Error\r\n'
            'ActionID: ' + actionid + '\r\n'
            'foo bar\nbaz quux\n--END COMMAND--\r\n'
            '\r\n'
        )
        self.assertTrue(lose.called)
        self.assertEqual(len(self.flushLoggedErrors(ProtocolError)), 1)


    def test_actionNoBodyOnFollowsIsError(self):
        """Connection is dropped on a Follows response without a body"""

        d, actionid = self._startAndSendAction()
        lose = self.transport.loseConnection = Mock()
        self.protocol.dataReceived(
            'Response: Follows\r\n'
            'ActionID: ' + actionid + '\r\n'
            '\r\n'
        )
        self.assertTrue(lose.called)
        self.assertEqual(len(self.flushLoggedErrors(ProtocolError)), 1)


    def test_badResponse(self):
        """Connection is dropped on a bad response"""

        d, actionid = self._startAndSendAction()
        lose = self.transport.loseConnection = Mock()
        self.protocol.dataReceived(
            'Response: Foobar\r\n'
            'ActionID: ' + actionid + '\r\n'
            '\r\n'
        )
        self.assertTrue(lose.called)
        self.assertEqual(len(self.flushLoggedErrors(ProtocolError)), 1)


# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
