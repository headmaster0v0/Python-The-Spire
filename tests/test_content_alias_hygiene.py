from __future__ import annotations

from sts_py.engine.content.card_instance import CardInstance
from sts_py.engine.content.cards_min import CARD_ID_ALIASES


class TestContentAliasHygiene:
    def test_remaining_legacy_aliases_resolve_through_alias_table_and_runtime(self):
        expected_aliases = {
            "AThousandCuts": "ThousandCuts",
            "CripplingPoison": "CripplingCloud",
            "LockOn": "Lockon",
            "Impulse": "Darkness",
            "ThunderStrike": "Tempest",
        }

        for alias_id, runtime_id in expected_aliases.items():
            assert CARD_ID_ALIASES[alias_id] == runtime_id
            assert CardInstance(alias_id).card_id == runtime_id

    def test_starter_aliases_remain_pinned(self):
        expected_aliases = {
            "Strike_Green": "Strike",
            "Defend_Green": "Defend",
            "Strike_Red": "Strike",
            "Defend_Red": "Defend",
        }

        for alias_id, runtime_id in expected_aliases.items():
            assert CARD_ID_ALIASES[alias_id] == runtime_id
            assert CardInstance(alias_id).card_id == runtime_id
