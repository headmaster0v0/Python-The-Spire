from __future__ import annotations

"""Generate map image using original game sprites."""

import os
import zipfile
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _find_project_root() -> Path:
    path = Path(__file__).resolve().parent
    markers = ("desktop-1.0.jar", "desktop-1.0-decompiled")
    while True:
        if any((path / marker).exists() for marker in markers):
            return path
        if path.parent == path:
            return Path(__file__).resolve().parent
        path = path.parent


PROJECT_ROOT = _find_project_root()
DECOMPILED_ASSETS_DIR = PROJECT_ROOT / "desktop-1.0-decompiled" / "images" / "ui" / "map"
JAR_PATH = PROJECT_ROOT / "desktop-1.0.jar"
EXTRACT_ROOT = PROJECT_ROOT / "runtime_tmp" / "map_asset_cache"
EXTRACTED_ASSETS_DIR = EXTRACT_ROOT / "images" / "ui" / "map"

NODE_IMAGES = {
    "M": "monster.png",
    "E": "elite.png",
    "?": "event.png",
    "$": "shop.png",
    "R": "rest.png",
    "T": "chest.png",
    "B": None,
}

BOSS_IMAGES = {
    1: {0: os.path.join("boss", "hexaghost.png"), 1: os.path.join("boss", "slime.png"), 2: os.path.join("boss", "guardian.png")},
    2: {0: os.path.join("boss", "champ.png"), 1: os.path.join("boss", "collector.png"), 2: os.path.join("boss", "automaton.png")},
    3: {0: os.path.join("boss", "awakened.png"), 1: os.path.join("boss", "timeeater.png"), 2: os.path.join("boss", "donu.png")},
}

NODE_OUTLINE_IMAGES = {
    "M": "monsterOutline.png",
    "E": "eliteOutline.png",
    "?": "eventOutline.png",
    "$": "shopOutline.png",
    "R": "restOutline.png",
    "T": "chestOutline.png",
}

NODE_SIZE = 200
BOSS_SIZE = 250
LINE_WIDTH = 12
PADDING = 80
BOSS_PADDING = 160


def _map_asset_files() -> set[str]:
    names = {
        file_name
        for file_name in NODE_IMAGES.values()
        if file_name
    }
    names.update(NODE_OUTLINE_IMAGES.values())
    for boss_images in BOSS_IMAGES.values():
        names.update(boss_images.values())
    return {(Path("images") / "ui" / "map" / Path(name)).as_posix() for name in names}


def _extract_map_assets_from_jar(jar_path: Path, extract_root: Path) -> Path:
    extract_root.mkdir(parents=True, exist_ok=True)
    required_assets = _map_asset_files()
    if all((extract_root / relative).exists() for relative in required_assets):
        return extract_root / "images" / "ui" / "map"

    with zipfile.ZipFile(jar_path) as jar:
        for relative in sorted(required_assets):
            target = extract_root / relative
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with jar.open(relative) as src, target.open("wb") as dst:
                dst.write(src.read())
    return extract_root / "images" / "ui" / "map"


def _resolve_assets_dir() -> Path:
    if DECOMPILED_ASSETS_DIR.exists():
        return DECOMPILED_ASSETS_DIR
    if JAR_PATH.exists():
        return _extract_map_assets_from_jar(JAR_PATH, EXTRACT_ROOT)
    return DECOMPILED_ASSETS_DIR


ASSETS_DIR = _resolve_assets_dir()


@lru_cache(maxsize=None)
def load_image(name: str) -> Image.Image | None:
    if name is None:
        return None
    path = ASSETS_DIR / os.path.normpath(name)
    if not path.exists():
        return None
    with Image.open(path) as source:
        img = source.convert("RGBA")
    return adjust_image_contrast(img)


@lru_cache(maxsize=None)
def _load_resized_image(name: str | None, width: int, height: int) -> Image.Image | None:
    if name is None:
        return None
    img = load_image(name)
    if img is None:
        return None
    return img.resize((width, height), Image.LANCZOS)


def adjust_image_contrast(img: Image.Image, brightness: float = 1.0) -> Image.Image:
    import numpy as np
    arr = np.array(img)
    if arr.shape[2] != 4:
        return img

    rgb = arr[:, :, :3].astype(np.float32)
    alpha = arr[:, :, 3]

    rgb = rgb * brightness
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


def draw_curved_line(draw: ImageDraw.Draw, x1: int, y1: int, x2: int, y2: int, color: tuple, width: int = LINE_WIDTH):
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)


def _draw_node_highlight(draw: ImageDraw.Draw, px: int, py: int, *, is_current: bool, is_available: bool) -> None:
    if not is_current and not is_available:
        return
    if is_current:
        padding = 18
        fill = (255, 241, 188, 120)
        outline = (255, 255, 255, 230)
        width = 10
    else:
        padding = 10
        fill = (145, 214, 255, 72)
        outline = (217, 242, 255, 190)
        width = 6
    draw.ellipse(
        (px - padding, py - padding, px + NODE_SIZE + padding, py + NODE_SIZE + padding),
        fill=fill,
        outline=outline,
        width=width,
    )


def generate_map_image(engine) -> Image.Image:
    nodes = engine.state.map_nodes
    if not nodes:
        return Image.new("RGBA", (800, 600), (50, 50, 50, 255))

    node_map = {n.node_id: n for n in nodes}
    floors_y: dict[int, list] = {}
    for n in nodes:
        floors_y.setdefault(n.y, []).append(n)

    current_node_idx = engine.state.current_node_idx
    available_ids = {n.node_id for n in engine.get_available_paths()}
    min_y = min(floors_y.keys())
    max_y = max(floors_y.keys())
    max_x = max(n.x for n in nodes)

    act_boss_idx = engine.state.seed % 3

    node_spacing_x = 200
    node_spacing_y = 180
    start_x = PADDING + 100
    start_y = BOSS_PADDING + 100

    img_width = start_x * 2 + max_x * node_spacing_x + NODE_SIZE
    img_height = start_y + (max_y - min_y + 1) * node_spacing_y + PADDING + NODE_SIZE

    bg = Image.new("RGBA", (img_width, img_height), (210, 180, 140, 255))

    line_color = (100, 70, 40, 255)
    draw = ImageDraw.Draw(bg)

    for node in nodes:
        for dst in node.connections:
            dst_node = node_map[dst]
            if dst_node.y != node.y + 1:
                continue

            px1 = start_x + node.x * node_spacing_x + NODE_SIZE // 2
            py1 = start_y + (max_y - node.y) * node_spacing_y + NODE_SIZE // 2
            px2 = start_x + dst_node.x * node_spacing_x + NODE_SIZE // 2
            py2 = start_y + (max_y - dst_node.y) * node_spacing_y + NODE_SIZE // 2

            draw_curved_line(draw, px1, py1, px2, py2, line_color)

    for y in range(max_y, min_y - 1, -1):
        node_list = floors_y.get(y, [])
        if not node_list:
            continue

        for node in node_list:
            px = start_x + node.x * node_spacing_x
            py = start_y + (max_y - y) * node_spacing_y

            is_current = node.node_id == current_node_idx
            is_available = node.node_id in available_ids
            is_boss = y == max_y

            _draw_node_highlight(draw, px, py, is_current=is_current, is_available=is_available)

            if is_boss:
                boss_img = _load_resized_image(BOSS_IMAGES.get(engine.state.act, BOSS_IMAGES[1]).get(act_boss_idx), BOSS_SIZE, BOSS_SIZE)
                if boss_img:
                    boss_paste_x = px + (NODE_SIZE - BOSS_SIZE) // 2
                    boss_paste_y = py + (NODE_SIZE - BOSS_SIZE) // 2
                    bg.paste(boss_img, (boss_paste_x, boss_paste_y), boss_img)
            else:
                node_key = node.room_type.value

                if is_current:
                    node_outline = _load_resized_image(NODE_OUTLINE_IMAGES.get(node_key), NODE_SIZE, NODE_SIZE)
                    if node_outline:
                        bg.paste(node_outline, (px, py), node_outline)

                node_img = _load_resized_image(NODE_IMAGES.get(node_key), NODE_SIZE, NODE_SIZE)
                if node_img:
                    bg.paste(node_img, (px, py), node_img)

    try:
        title_font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        title_font = ImageFont.load_default()

    act_names = {1: "低语者之域", 2: "城市", 3: "彼方"}
    title = f"第 {engine.state.act} 幕 - {act_names.get(engine.state.act, '???')}"

    draw.text((img_width // 2 - 100, 20), title, font=title_font, fill=(255, 255, 255, 255))

    return bg


def save_map_image(engine, path: str | os.PathLike[str] = "map_output.png") -> str:
    img = generate_map_image(engine)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    img.save(destination)
    return str(destination.resolve())


def show_map_image(engine):
    path = save_map_image(engine)
    os.startfile(path)
