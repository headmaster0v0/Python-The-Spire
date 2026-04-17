from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sts_py.tools.autosave_decode import SaveSeedCounters


@dataclass(frozen=True)
class CardChoiceMetric:
    floor: int
    picked: str
    not_picked: tuple[str, str]

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CardChoiceMetric":
        np = d.get("not_picked") or []
        return CardChoiceMetric(
            floor=int(d.get("floor")),
            picked=str(d.get("picked")),
            not_picked=(str(np[0]), str(np[1])),
        )


@dataclass(frozen=True)
class RunSnapshot:
    seed: int
    seed_set: bool

    floor_num: int
    act_num: int
    current_room: str

    current_health: int
    max_health: int
    gold: int

    neow_bonus: str | None
    neow_cost: str | None

    deck_ids: tuple[str, ...]
    relic_ids: tuple[str, ...]

    rng: SaveSeedCounters

    path_taken: tuple[str, ...]
    card_choices: tuple[CardChoiceMetric, ...]
    damage_taken: tuple[dict[str, Any], ...]

    @staticmethod
    def from_autosave(d: dict[str, Any]) -> "RunSnapshot":
        seed = int(d.get("seed"))
        seed_set = bool(d.get("seed_set"))

        cards = d.get("cards") or []
        deck_ids = tuple(str(c.get("id")) for c in cards)
        relics = d.get("relics") or []
        relic_ids = tuple(str(r) for r in relics)

        metrics = {
            "path_taken": d.get("metric_path_taken") or [],
            "card_choices": d.get("metric_card_choices") or [],
            "damage_taken": d.get("metric_damage_taken") or [],
        }

        rng = SaveSeedCounters.from_save(d)

        return RunSnapshot(
            seed=seed,
            seed_set=seed_set,
            floor_num=int(d.get("floor_num")),
            act_num=int(d.get("act_num")),
            current_room=str(d.get("current_room")),
            current_health=int(d.get("current_health")),
            max_health=int(d.get("max_health")),
            gold=int(d.get("gold")),
            neow_bonus=d.get("neow_bonus"),
            neow_cost=d.get("neow_cost"),
            deck_ids=deck_ids,
            relic_ids=relic_ids,
            rng=rng,
            path_taken=tuple(str(x) for x in metrics["path_taken"]),
            card_choices=tuple(CardChoiceMetric.from_dict(x) for x in metrics["card_choices"]),
            damage_taken=tuple(metrics["damage_taken"]),
        )
