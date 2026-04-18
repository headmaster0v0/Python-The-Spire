from __future__ import annotations

"""Generate map image using original game sprites."""

import os
from PIL import Image, ImageDraw, ImageFont

def _find_project_root() -> str:
    path = os.getcwd()
    while path and not os.path.exists(os.path.join(path, 'desktop-1.0-decompiled')):
        parent = os.path.dirname(path)
        if parent == path:
            break
        path = parent
    return path


ASSETS_DIR = os.path.join(_find_project_root(), "desktop-1.0-decompiled", "images", "ui", "map")

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


def load_image(name: str) -> Image.Image | None:
    if name is None:
        return None
    path = os.path.join(ASSETS_DIR, os.path.normpath(name))
    if not os.path.exists(path):
        return None
    img = Image.open(path).convert("RGBA")
    return adjust_image_contrast(img)


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

    for node in nodes:
        for dst in node.connections:
            dst_node = node_map[dst]
            if dst_node.y != node.y + 1:
                continue

            px1 = start_x + node.x * node_spacing_x + NODE_SIZE // 2
            py1 = start_y + (max_y - node.y) * node_spacing_y + NODE_SIZE // 2
            px2 = start_x + dst_node.x * node_spacing_x + NODE_SIZE // 2
            py2 = start_y + (max_y - dst_node.y) * node_spacing_y + NODE_SIZE // 2

            draw = ImageDraw.Draw(bg)
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

            if is_boss:
                boss_img = load_image(BOSS_IMAGES.get(engine.state.act, BOSS_IMAGES[1]).get(act_boss_idx))
                if boss_img:
                    boss_scaled = boss_img.resize((BOSS_SIZE, BOSS_SIZE), Image.LANCZOS)
                    boss_paste_x = px + (NODE_SIZE - BOSS_SIZE) // 2
                    boss_paste_y = py + (NODE_SIZE - BOSS_SIZE) // 2
                    bg.paste(boss_scaled, (boss_paste_x, boss_paste_y), boss_scaled)
            else:
                node_key = node.room_type.value

                if is_current:
                    node_outline = load_image(NODE_OUTLINE_IMAGES.get(node_key))
                    if node_outline:
                        outline_scaled = node_outline.resize((NODE_SIZE, NODE_SIZE), Image.LANCZOS)
                        bg.paste(outline_scaled, (px, py), outline_scaled)

                node_img = load_image(NODE_IMAGES.get(node_key))
                if node_img:
                    node_scaled = node_img.resize((NODE_SIZE, NODE_SIZE), Image.LANCZOS)
                    bg.paste(node_scaled, (px, py), node_scaled)

    try:
        title_font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        title_font = ImageFont.load_default()

    act_names = {1: "低语者之域", 2: "城市", 3: "彼方"}
    title = f"第 {engine.state.act} 幕 - {act_names.get(engine.state.act, '???')}"

    draw = ImageDraw.Draw(bg)
    draw.text((img_width // 2 - 100, 20), title, font=title_font, fill=(255, 255, 255, 255))

    return bg


def save_map_image(engine, path: str = "map_output.png") -> str:
    img = generate_map_image(engine)
    img.save(path)
    return os.path.abspath(path)


def show_map_image(engine):
    path = save_map_image(engine)
    os.startfile(path)
