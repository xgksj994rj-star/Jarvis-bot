import unittest
from unittest.mock import Mock, patch

import actions.discord_integration as discord_integration
from actions.discord_integration import DiscordBot


class DiscordVoicePacketTests(unittest.TestCase):
    def test_register_discord_voice_receive_is_opt_in(self):
        bot = DiscordBot()
        fake_voice_client = Mock()
        fake_voice_client.channel = Mock()
        fake_voice_client.channel.name = "Test Voice"

        with patch.object(discord_integration, "_DISCORD_VOICE_RECEIVE_ENABLED", False):
            bot._register_discord_voice_receive(fake_voice_client)

        fake_voice_client._connection.add_socket_listener.assert_not_called()

    def test_on_discord_voice_packet_decrypts_inline_and_enqueues_fragment(self):
        bot = DiscordBot()
        bot._loop = Mock()
        bot._loop.is_closed.return_value = False

        fake_voice_client = Mock()
        fake_voice_client.channel = Mock()
        fake_voice_client.channel.name = "Test Voice"

        decrypted_packet = b"decrypted-packet"

        with patch.object(bot, "_decrypt_discord_voice_packet", return_value=(decrypted_packet, 42)) as decrypt_mock, \
             patch.object(bot, "_extract_opus_payload_from_rtp", return_value=b"opus-fragment") as extract_mock:
            bot._on_discord_voice_packet(b"raw-packet", fake_voice_client)

        decrypt_mock.assert_called_once_with(b"raw-packet", fake_voice_client)
        extract_mock.assert_called_once_with(decrypted_packet)
        bot._loop.call_soon_threadsafe.assert_called_once_with(
            bot._enqueue_discord_voice_packet,
            42,
            b"opus-fragment",
            fake_voice_client,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
