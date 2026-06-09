import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import actions.discord_integration as discord_integration


class ReactionRoleSettingsTests(unittest.TestCase):
    def test_parse_reaction_role_options_accepts_bulk_input(self):
        entries = discord_integration._parse_reaction_role_options("😀@Players\n😎@Mods;🤖@Staff")

        self.assertEqual([(emoji, role_name) for emoji, role_name in entries], [
            ("😀", "Players"),
            ("😎", "Mods"),
            ("🤖", "Staff"),
        ])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name) / "discord_data.json"
        self.patcher = mock.patch.object(discord_integration, "DEFAULT_DISCORD_DATA_FILE", self.temp_path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_reaction_role_menu_options_are_stored(self):
        discord_integration._add_reaction_role(
            "guild-1",
            42,
            "🎉",
            99,
            single_choice=True,
            remove_on_unreact=False,
        )

        settings = discord_integration._get_reaction_role_menu_settings("guild-1", 42)

        self.assertTrue(settings["single_choice"])
        self.assertFalse(settings["remove_on_unreact"])
        self.assertEqual(discord_integration._get_reaction_role("guild-1", 42, "🎉"), 99)

    def test_owner_is_recognized_from_user_object(self):
        class DummyUser:
            def __init__(self, user_id):
                self.id = user_id

        owner = DummyUser(int(discord_integration.OWNER_DISCORD_ID))
        self.assertTrue(discord_integration._is_owner(owner))

    def test_parse_select_emoji_accepts_unicode(self):
        emoji = discord_integration._parse_select_emoji("🌎")
        self.assertEqual(emoji, "🌎")

    def test_reaction_role_menu_settings_default_to_enabled_removal(self):
        discord_integration._add_reaction_role("guild-1", 42, "🎉", 99)

        settings = discord_integration._get_reaction_role_menu_settings("guild-1", 42)

        self.assertFalse(settings["single_choice"])
        self.assertTrue(settings["remove_on_unreact"])


if __name__ == "__main__":
    unittest.main()
