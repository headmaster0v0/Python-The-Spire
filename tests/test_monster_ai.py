"""Verify all monster AI implementations work correctly."""
from __future__ import annotations

import pytest
from sts_py.engine.core.rng import MutableRNG
from sts_py.engine.monsters.monster_base import MonsterMove
from sts_py.engine.monsters.intent import MonsterIntent
from sts_py.engine.monsters.exordium import (
    JawWorm, LouseNormal, Cultist, SlaverRed, GremlinNob,
    Lagavulin, Sentry, FungiBeast, LouseDefensive, SlaverBlue
)
from sts_py.engine.monsters.bosses import (
    Hexaghost, SlimeBoss, TheGuardian, Champ, Collector,
    Automaton, BronzeOrb, TorchHead, AwakenedOne, TimeEater, DonuAndDeca, Deca, Donu
)
from sts_py.engine.monsters.city_beyond import (
    GremlinLeader, SphericGuardian, Chosen, ShellParasite, Byrd, SnakePlant,
    Snecko, Centurion, Healer, Darkling, OrbWalker, Maw,
    GiantHead, Nemesis, Reptomancer, WrithingMass
)


class TestMonsterAI:
    """Test that all monsters can execute their AI logic without errors."""

    def test_jaw_worm_ai(self):
        """Jaw Worm AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(123, rng_type="monster")
        worm = JawWorm.create(rng, ascension=0)

        for _ in range(10):
            worm.roll_move(rng)

        assert worm.next_move is not None
        assert len(worm.move_history) == 10

    def test_louse_normal_ai(self):
        """Louse AI can execute get_move() and has curl_up."""
        rng = MutableRNG.from_seed(456, rng_type="monster")
        louse = LouseNormal.create(rng, ascension=0)

        for i in range(5):
            louse.roll_move(rng)
            assert louse.curl_up > 0

    def test_cultist_ai(self):
        """Cultist AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(789, rng_type="monster")
        cultist = Cultist.create(rng, ascension=0)

        cultist.roll_move(rng)
        assert cultist.next_move is not None

        for _ in range(5):
            cultist.roll_move(rng)
            assert cultist.next_move is not None

    def test_slaver_red_ai(self):
        """Red Slaver AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(111, rng_type="monster")
        slaver = SlaverRed.create(rng, ascension=0)

        for _ in range(5):
            slaver.roll_move(rng)
            assert slaver.next_move is not None

    def test_gremlin_nob_ai(self):
        """Gremlin Nob AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(222, rng_type="monster")
        nob = GremlinNob.create(rng, ascension=0)

        for _ in range(5):
            nob.roll_move(rng)
            assert nob.next_move is not None

    def test_lagavulin_ai(self):
        """Lagavulin AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(333, rng_type="monster")
        lag = Lagavulin.create(rng, ascension=0)

        lag.roll_move(rng)
        assert lag.next_move is not None

    def test_sentry_ai(self):
        """Sentry AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(444, rng_type="monster")
        sentry = Sentry.create(rng, ascension=0)

        for _ in range(5):
            sentry.roll_move(rng)
            assert sentry.next_move is not None

    def test_fungi_beast_ai(self):
        """Fungi Beast AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(555, rng_type="monster")
        fungi = FungiBeast.create(rng, ascension=0)

        for _ in range(5):
            fungi.roll_move(rng)
            assert fungi.next_move is not None

    def test_louse_defensive_ai(self):
        """Defensive Louse AI has curl_up and can execute get_move()."""
        rng = MutableRNG.from_seed(666, rng_type="monster")
        louse = LouseDefensive.create(rng, ascension=0)

        assert louse.curl_up > 0
        for _ in range(5):
            louse.roll_move(rng)

    def test_slaver_blue_ai(self):
        """Blue Slaver AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(777, rng_type="monster")
        slaver = SlaverBlue.create(rng, ascension=0)

        for _ in range(5):
            slaver.roll_move(rng)
            assert slaver.next_move is not None


class TestBossAI:
    """Test that all bosses have working AI."""

    def test_hexaghost_ai(self):
        """Hexaghost AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(1001, rng_type="monster")
        ghost = Hexaghost.create(rng, ascension=0)

        ghost.roll_move(rng)
        assert ghost.next_move is not None

        for _ in range(10):
            ghost.roll_move(rng)
            assert ghost.next_move is not None

    def test_slime_boss_ai(self):
        """Slime Boss AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(1002, rng_type="monster")
        slime = SlimeBoss.create(rng, ascension=0)

        slime.roll_move(rng)
        assert slime.next_move is not None

        slime.hp = slime.max_hp // 2
        slime.roll_move(rng)
        assert slime.next_move is not None

    def test_the_guardian_ai(self):
        """The Guardian AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(1003, rng_type="monster")
        guardian = TheGuardian.create(rng, ascension=0)

        for _ in range(5):
            guardian.roll_move(rng)
            assert guardian.next_move is not None

    def test_champ_ai(self):
        """Champ AI can execute get_move() and changes phase."""
        rng = MutableRNG.from_seed(1004, rng_type="monster")
        champ = Champ.create(rng, ascension=0)

        champ.roll_move(rng)
        assert champ.next_move is not None

        champ.hp = champ.max_hp // 2
        champ.roll_move(rng)
        assert champ.phase == 1

    def test_collector_ai(self):
        """Collector AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(1005, rng_type="monster")
        collector = Collector.create(rng, ascension=0)

        for _ in range(5):
            collector.roll_move(rng)
            assert collector.next_move is not None

    def test_automaton_ai(self):
        """Automaton AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(1006, rng_type="monster")
        auto = Automaton.create(rng, ascension=0)

        for _ in range(5):
            auto.roll_move(rng)
            assert auto.next_move is not None

    def test_awakened_one_ai(self):
        """Awakened One AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(1007, rng_type="monster")
        awakened = AwakenedOne.create(rng, ascension=0)

        for _ in range(5):
            awakened.roll_move(rng)
            assert awakened.next_move is not None

    def test_time_eater_ai(self):
        """Time Eater AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(1008, rng_type="monster")
        eater = TimeEater.create(rng, ascension=0)

        for _ in range(5):
            eater.roll_move(rng)
            assert eater.next_move is not None

    def test_donu_and_deca_ai(self):
        """Donu and Deca AI can execute get_move() without errors."""
        rng = MutableRNG.from_seed(1009, rng_type="monster")
        donu = DonuAndDeca.create(rng, ascension=0)

        for _ in range(6):
            donu.roll_move(rng)
            assert donu.next_move is not None

    def test_collector_script_summons_minions_and_unlocks_mega_debuff(self):
        from sts_py.engine.combat.combat_engine import CombatEngine

        rng = MutableRNG.from_seed(1010, rng_type="monster")
        collector = Collector.create(rng, ascension=0)
        combat = CombatEngine.create_with_monsters(
            monsters=[collector],
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(1010, counter=0),
            hp_rng=MutableRNG.from_seed(1010, counter=100),
        )
        player = combat.state.player

        collector.set_move(MonsterMove(1, MonsterIntent.UNKNOWN, name="Summon"))
        collector.take_turn(player)
        assert [monster.id for monster in combat.state.monsters].count("TorchHead") == 2

        collector.initial_spawn = False
        collector.turns_taken = 3
        collector.get_move(0)
        assert collector.next_move is not None
        assert collector.next_move.move_id == 4
        assert collector.next_move.intent == MonsterIntent.STRONG_DEBUFF

    def test_automaton_script_spawns_bronze_orbs_and_reaches_hyper_beam(self):
        from sts_py.engine.combat.combat_engine import CombatEngine

        rng = MutableRNG.from_seed(1011, rng_type="monster")
        automaton = Automaton.create(rng, ascension=0)
        combat = CombatEngine.create_with_monsters(
            monsters=[automaton],
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(1011, counter=0),
            hp_rng=MutableRNG.from_seed(1011, counter=100),
        )
        player = combat.state.player

        automaton.set_move(MonsterMove(4, MonsterIntent.UNKNOWN, name="Spawn Orbs"))
        automaton.take_turn(player)
        assert sum(1 for monster in combat.state.monsters if monster.id == "BronzeOrb") == 2

        automaton.num_turns = 4
        automaton.get_move(0)
        assert automaton.next_move is not None
        assert automaton.next_move.move_id == 2
        assert automaton.next_move.base_damage == automaton.hyper_beam_dmg

    def test_bronze_orb_stasis_steals_and_returns_a_card_on_death(self):
        from sts_py.engine.combat.combat_engine import CombatEngine
        from sts_py.engine.content.card_instance import CardInstance

        rng = MutableRNG.from_seed(10115, rng_type="monster")
        automaton = Automaton.create(rng, ascension=0)
        orb = BronzeOrb.create(rng, ascension=0)
        combat = CombatEngine.create_with_monsters(
            monsters=[automaton, orb],
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(10115, counter=0),
            hp_rng=MutableRNG.from_seed(10115, counter=100),
        )
        combat.state.card_manager.draw_pile.clear()
        combat.state.card_manager.draw_pile.add(CardInstance(card_id="Bash"))
        hand_before = combat.state.card_manager.hand.size()

        orb.set_move(MonsterMove(3, MonsterIntent.STRONG_DEBUFF, name="Stasis"))
        orb.take_turn(combat.state.player)
        assert combat.state.card_manager.draw_pile.is_empty()
        assert orb.stasis_card is not None

        orb.on_death()
        assert combat.state.card_manager.hand.size() == hand_before + 1
        assert any(card.card_id == "Bash" for card in combat.state.card_manager.hand.cards)

    def test_awakened_one_rebirth_and_curiosity_strength_gain(self):
        from sts_py.engine.combat.combat_engine import CombatEngine
        from sts_py.engine.content.card_instance import CardInstance

        rng = MutableRNG.from_seed(1012, rng_type="monster")
        awakened = AwakenedOne.create(rng, ascension=4)
        combat = CombatEngine.create_with_monsters(
            monsters=[awakened],
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(1012, counter=0),
            hp_rng=MutableRNG.from_seed(1012, counter=100),
        )
        assert awakened.get_effective_strength() >= 2

        awakened.on_player_power_played(CardInstance(card_id="Inflame"))
        assert awakened.get_effective_strength() >= 3

        awakened.take_damage(awakened.max_hp + 50)
        assert awakened.half_dead is True
        assert awakened.next_move is not None
        assert awakened.next_move.move_id == 3

        awakened.take_turn(combat.state.player)
        assert awakened.form1 is False
        assert awakened.half_dead is False
        assert awakened.hp == awakened.max_hp

    def test_time_eater_haste_and_head_slam_side_effects(self):
        from sts_py.engine.combat.combat_engine import CombatEngine

        rng = MutableRNG.from_seed(1013, rng_type="monster")
        eater = TimeEater.create(rng, ascension=19)
        combat = CombatEngine.create_with_monsters(
            monsters=[eater],
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(1013, counter=0),
            hp_rng=MutableRNG.from_seed(1013, counter=100),
        )
        player = combat.state.player

        assert int(getattr(player, "_cards_play_limit", 0) or 0) == 12

        eater.hp = eater.max_hp // 2 - 1
        eater.get_move(0)
        assert eater.next_move is not None
        assert eater.next_move.move_id == 5

        eater.set_move(MonsterMove(4, MonsterIntent.ATTACK_DEBUFF, eater.head_slam_dmg, name="Head Slam"))
        eater.take_turn(player)
        assert int(getattr(player, "_draw_reduction_next_turn", 0) or 0) == 1
        assert combat.state.card_manager.discard_pile.size() >= 2


class TestAct2Act3MonsterAI:
    """Test ACT 2 and ACT 3 monster AI."""

    def test_spheric_guardian_ai(self):
        """Spheric Guardian AI can execute get_move()."""
        rng = MutableRNG.from_seed(2001, rng_type="monster")
        m = SphericGuardian.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_spheric_guardian_prebattle_and_java_move_cycle(self):
        from sts_py.engine.combat.combat_engine import CombatEngine

        rng = MutableRNG.from_seed(20015, rng_type="monster")
        guardian = SphericGuardian.create(rng, 17)
        combat = CombatEngine.create_with_monsters(
            monsters=[guardian],
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(20015, counter=0),
            hp_rng=MutableRNG.from_seed(20015, counter=100),
        )

        assert guardian.block == 40
        assert guardian.get_power_amount("Artifact") == 3

        guardian.move_history.clear()
        guardian.first_move = True
        guardian.second_move = True
        guardian.get_move(0)
        assert guardian.next_move is not None
        assert guardian.next_move.move_id == 2
        assert guardian.next_move.intent == MonsterIntent.DEFEND

        guardian.get_move(99)
        assert guardian.next_move is not None
        assert guardian.next_move.move_id == 4
        assert guardian.next_move.intent == MonsterIntent.ATTACK_DEBUFF

        guardian.get_move(99)
        assert guardian.next_move is not None
        assert guardian.next_move.move_id == 1
        assert guardian.next_move.multiplier == 2

    def test_chosen_ai(self):
        """Chosen AI can execute get_move()."""
        rng = MutableRNG.from_seed(2002, rng_type="monster")
        m = Chosen.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_shell_parasite_ai(self):
        """Shell Parasite AI can execute get_move()."""
        rng = MutableRNG.from_seed(2003, rng_type="monster")
        m = ShellParasite.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_byrd_ai(self):
        """Byrd AI can execute get_move()."""
        rng = MutableRNG.from_seed(2004, rng_type="monster")
        m = Byrd.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_snake_plant_ai(self):
        """Snake Plant AI can execute get_move()."""
        rng = MutableRNG.from_seed(2005, rng_type="monster")
        m = SnakePlant.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_snecko_ai(self):
        """Snecko AI can execute get_move()."""
        rng = MutableRNG.from_seed(2006, rng_type="monster")
        m = Snecko.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_centurion_ai(self):
        """Centurion AI can execute get_move()."""
        rng = MutableRNG.from_seed(2007, rng_type="monster")
        m = Centurion.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_healer_ai(self):
        """Healer AI can execute get_move()."""
        rng = MutableRNG.from_seed(2008, rng_type="monster")
        m = Healer.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_darkling_ai(self):
        """Darkling AI can execute get_move()."""
        rng = MutableRNG.from_seed(3001, rng_type="monster")
        m = Darkling.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_orb_walker_ai(self):
        """Orb Walker AI can execute get_move()."""
        rng = MutableRNG.from_seed(3002, rng_type="monster")
        m = OrbWalker.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_maw_ai(self):
        """Maw AI can execute get_move()."""
        rng = MutableRNG.from_seed(3003, rng_type="monster")
        m = Maw.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_giant_head_ai(self):
        """Giant Head AI can execute get_move()."""
        rng = MutableRNG.from_seed(3004, rng_type="monster")
        m = GiantHead.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_nemesis_ai(self):
        """Nemesis AI can execute get_move()."""
        rng = MutableRNG.from_seed(3005, rng_type="monster")
        m = Nemesis.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_reptomancer_ai(self):
        """Reptomancer AI can execute get_move()."""
        rng = MutableRNG.from_seed(3006, rng_type="monster")
        m = Reptomancer.create(rng, 0)
        for _ in range(5):
            m.roll_move(rng)
            assert m.next_move is not None

    def test_gremlin_leader_can_choose_attack_branch_when_gremlins_are_alive(self):
        from sts_py.engine.combat.combat_engine import CombatEngine
        from sts_py.engine.monsters.exordium import GremlinFat, GremlinWar

        rng = MutableRNG.from_seed(30065, rng_type="monster")
        leader = GremlinLeader.create(rng, 0)
        combat = CombatEngine.create_with_monsters(
            monsters=[GremlinFat.create(rng, 0), GremlinWar.create(rng, 0), leader],
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(30065, counter=0),
            hp_rng=MutableRNG.from_seed(30065, counter=100),
        )

        leader.move_history.clear()
        leader.first_move = False
        leader.get_move(90)
        assert leader.next_move is not None
        assert leader.next_move.move_id == 4
        assert leader.next_move.intent == MonsterIntent.ATTACK
        assert leader.next_move.multiplier == 3
        assert len(combat.state.monsters) == 3

    def test_writhing_mass_first_move_matches_java_branches(self):
        rng = MutableRNG.from_seed(3007, rng_type="monster")
        m = WrithingMass.create(rng, 0)

        m.get_move(0)
        assert m.next_move is not None
        assert m.next_move.move_id == 1
        assert m.next_move.intent == MonsterIntent.ATTACK
        assert m.next_move.multiplier == 3

        m = WrithingMass.create(rng, 0)
        m.get_move(40)
        assert m.next_move is not None
        assert m.next_move.move_id == 2
        assert m.next_move.intent == MonsterIntent.ATTACK_DEFEND

        m = WrithingMass.create(rng, 0)
        m.get_move(90)
        assert m.next_move is not None
        assert m.next_move.move_id == 3
        assert m.next_move.intent == MonsterIntent.ATTACK_DEBUFF

    def test_donu_buff_increases_next_attack_damage(self):
        rng = MutableRNG.from_seed(3008, rng_type="monster")
        deca = Deca.create(rng, ascension=0)
        donu = Donu.create(rng, ascension=0)
        from sts_py.engine.combat.combat_engine import CombatEngine

        combat = CombatEngine.create_with_monsters(
            monsters=[deca, donu],
            player_hp=80,
            player_max_hp=80,
            ai_rng=MutableRNG.from_seed(3008, counter=0),
            hp_rng=MutableRNG.from_seed(3008, counter=100),
        )
        player = combat.state.player

        donu.set_move(MonsterMove(2, MonsterIntent.BUFF, name="Circle of Power"))
        donu.take_turn(player)
        donu.get_move(0)

        assert donu.strength == 3
        assert donu.next_move is not None
        assert donu.next_move.move_id == 0
        assert donu.get_intent_damage() == 13


class TestAllMonsterCreation:
    """Verify all monsters can be created without errors."""

    def test_all_act1_monsters_can_be_created(self):
        """All ACT 1 monsters can be instantiated."""
        rng = MutableRNG.from_seed(9999, rng_type="monster")

        monsters = [
            JawWorm.create(rng, 0),
            LouseNormal.create(rng, 0),
            Cultist.create(rng, 0),
            SlaverRed.create(rng, 0),
            GremlinNob.create(rng, 0),
            Lagavulin.create(rng, 0),
            Sentry.create(rng, 0),
            FungiBeast.create(rng, 0),
            LouseDefensive.create(rng, 0),
            SlaverBlue.create(rng, 0),
        ]

        assert len(monsters) == 10
        for m in monsters:
            assert m.hp > 0
            assert m.max_hp > 0

    def test_all_bosses_can_be_created(self):
        """All bosses can be instantiated."""
        rng = MutableRNG.from_seed(8888, rng_type="monster")

        bosses = [
            Hexaghost.create(rng, 0),
            SlimeBoss.create(rng, 0),
            TheGuardian.create(rng, 0),
            Champ.create(rng, 0),
            Collector.create(rng, 0),
            Automaton.create(rng, 0),
            AwakenedOne.create(rng, 0),
            TimeEater.create(rng, 0),
            DonuAndDeca.create(rng, 0),
        ]

        assert len(bosses) == 9
        for b in bosses:
            assert b.hp > 0
            assert b.max_hp > 0
