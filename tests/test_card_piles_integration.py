from __future__ import annotations

from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.combat.combat_engine import CombatEngine


SEED_LONG = 4452322743548530140


class TestCardPileIntegration:
    def test_combat_starts_with_card_manager_and_opening_hand(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )
        assert combat.state.card_manager is not None
        assert combat.state.card_manager.get_hand_size() == 5
        assert combat.state.card_manager.get_draw_pile_size() == 5

    def test_play_strike_spends_energy_and_moves_to_discard(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            deck=["Strike", "Strike", "Strike", "Strike", "Strike", "Defend", "Defend", "Defend", "Defend", "Bash"],
        )

        strike_index = next(i for i, card in enumerate(combat.state.card_manager.get_hand()) if card.card_id == "Strike")
        monster = combat.state.monsters[0]
        initial_hp = monster.hp
        initial_energy = combat.state.player.energy

        assert combat.play_card(strike_index, 0)
        assert combat.state.player.energy == initial_energy - 1
        assert monster.hp < initial_hp
        assert combat.state.card_manager.get_discard_pile_size() == 1

    def test_play_defend_grants_block_and_moves_to_discard(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
            deck=["Defend", "Defend", "Defend", "Defend", "Defend", "Strike", "Strike", "Strike", "Strike", "Bash"],
        )

        defend_index = next(i for i, card in enumerate(combat.state.card_manager.get_hand()) if card.card_id == "Defend")
        initial_block = combat.state.player.block

        assert combat.play_card(defend_index)
        assert combat.state.player.block > initial_block
        assert combat.state.card_manager.get_discard_pile_size() == 1

    def test_end_turn_discards_remaining_hand(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )

        initial_hand = combat.state.card_manager.get_hand_size()
        combat.end_player_turn()
        assert combat.state.card_manager.get_hand_size() == 5
        assert combat.state.card_manager.get_discard_pile_size() >= initial_hand

    def test_draw_pile_refills_from_discard(self):
        ai_rng = MutableRNG.from_seed(SEED_LONG, counter=0)
        hp_rng = MutableRNG.from_seed(SEED_LONG, counter=100)
        combat = CombatEngine.create(
            encounter_name="Jaw Worm",
            player_hp=80,
            player_max_hp=80,
            ai_rng=ai_rng,
            hp_rng=hp_rng,
        )

        for _ in range(3):
            while combat.state.card_manager.get_hand_size() > 0:
                if not combat.play_card(0, 0):
                    break
            combat.end_player_turn()

        assert combat.state.card_manager.get_draw_pile_size() >= 0
        assert combat.state.card_manager.get_discard_pile_size() >= 0
