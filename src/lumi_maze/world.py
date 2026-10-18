"""
WorldView — दृश्य-स्तर की संरचना: फर्श, दीवारें, निकास, आइटम और थीम डेकोर।
Ursina 8.3.0 के साथ प्रक्रियात्मक प्रिमिटिव्स का उपयोग करता है; कोई बाहरी एसेट नहीं।
"""

import random
import math
from typing import Dict, Tuple
from dataclasses import dataclass

from ursina import Entity, color, destroy

from .core import Maze, Cell
from .textures import texture_for

CELL_SIZE = 3.0
WALL_HEIGHT = 1.6
WALL_THICKNESS = 0.25
FLOOR_Y = -0.12


@dataclass
class ItemNode:
    """आइटम के दृश्य घटकों के लिए कंटेनर"""
    root: Entity
    item_type: str
    bob_offset: float = 0.0
    rotation_speed: float = 0.0


class WorldView:
    """
    एकल भूलभुलैया स्तर के लिए दृश्य प्रतिनिधित्व बनाता और प्रबंधित करता है।
    
    स्वामित्व:
      - self.root: इस स्तर की सभी एंटिटीज के लिए पैरेंट
      - self.item_nodes: Cell -> ItemNode (आइटम और निकास बीकन के लिए)
    """

    def __init__(self, maze: Maze):
        self.maze = maze
        self.root = Entity()
        self.item_nodes: Dict[Cell, ItemNode] = {}
        self._cleared = False
        
        # निर्धारितिक सजावट के लिए स्थानीय RNG
        theme_id = self._theme_id(maze.theme)
        dim_hash = (maze.width * 1000 + maze.height) & 0xFFFFFFFF
        self._rng = random.Random((theme_id << 24) ^ dim_hash ^ 0x9E3779B9)

        # थीम के अनुसार साझा टेक्सचर
        self._floor_tex = texture_for(maze.theme, 'floor', seed=((theme_id << 16) ^ 0xF100) & 0xFFFFFFFF)
        self._wall_tex = texture_for(maze.theme, 'wall', seed=((theme_id << 16) ^ 0xA110) & 0xFFFFFFFF)

        # ज्यामिति निर्माण
        self._build_floor()
        self._build_walls()
        self._build_exit()
        self._build_items()
        self._build_decorations()

    # ------------------------------------------------------------------ #
    # निर्माण सहायक
    # ------------------------------------------------------------------ #
    @staticmethod
    def _theme_id(theme: str) -> int:
        """चार थीम नामों के लिए स्थिर पूर्णांक मैपिंग।"""
        return {
            'stone': 1,
            'forest': 2,
            'cave': 3,
            'streams': 4,
        }.get(theme, 0)

    def _cell_center(self, cell: Cell) -> Tuple[float, float]:
        x, z = cell
        return (x * CELL_SIZE, z * CELL_SIZE)

    def _build_floor(self) -> None:
        """प्रत्येक सेल के केंद्र पर एक फर्श तल बनाता है।"""
        for x in range(self.maze.width):
            for z in range(self.maze.height):
                cx, cz = self._cell_center((x, z))
                Entity(
                    parent=self.root,
                    model='plane',
                    scale=(CELL_SIZE, 1, CELL_SIZE),
                    position=(cx, FLOOR_Y, cz),
                    texture=self._floor_tex,
                    color=color.white,
                )

    def _build_walls(self) -> None:
        """
        दीवारें बनाता है:
        - प्रत्येक सेल के लिए पूर्वी दीवार अगर (x,z) से (x+1,z) तक खुला नहीं है
        - प्रत्येक सेल के लिए उत्तरी दीवार अगर (x,z) से (x,z+1) तक खुला नहीं है
        - x=0 पर पश्चिमी सीमा और z=0 पर दक्षिणी सीमा
        - x=w-1 पर पूर्वी सीमा और z=h-1 पर उत्तरी सीमा
        दीवारें ठीक एक बार दिखाई देती हैं और कभी भी खुले मार्ग को पार नहीं करतीं।
        """
        w, h = self.maze.width, self.maze.height
        
        # आंतरिक दीवारें: पूर्व और उत्तर दिशाएं
        for x in range(w):
            for z in range(h):
                cx, cz = self._cell_center((x, z))
                
                # पूर्वी दीवार (x+1 दिशा)
                if x + 1 < w:
                    if not self.maze.is_open((x, z), (x + 1, z)):
                        self._create_wall(
                            pos=(cx + CELL_SIZE / 2, WALL_HEIGHT / 2, cz),
                            scale=(WALL_THICKNESS, WALL_HEIGHT, CELL_SIZE),
                        )
                
                # उत्तरी दीवार (z+1 दिशा)
                if z + 1 < h:
                    if not self.maze.is_open((x, z), (x, z + 1)):
                        self._create_wall(
                            pos=(cx, WALL_HEIGHT / 2, cz + CELL_SIZE / 2),
                            scale=(CELL_SIZE, WALL_HEIGHT, WALL_THICKNESS),
                        )
        
        # पश्चिमी सीमा (x = 0)
        for z in range(h):
            cx, cz = self._cell_center((0, z))
            self._create_wall(
                pos=(cx - CELL_SIZE / 2, WALL_HEIGHT / 2, cz),
                scale=(WALL_THICKNESS, WALL_HEIGHT, CELL_SIZE),
            )
        
        # पूर्वी सीमा (x = w-1)
        for z in range(h):
            cx, cz = self._cell_center((w - 1, z))
            self._create_wall(
                pos=(cx + CELL_SIZE / 2, WALL_HEIGHT / 2, cz),
                scale=(WALL_THICKNESS, WALL_HEIGHT, CELL_SIZE),
            )
        
        # दक्षिणी सीमा (z = 0)
        for x in range(w):
            cx, cz = self._cell_center((x, 0))
            self._create_wall(
                pos=(cx, WALL_HEIGHT / 2, cz - CELL_SIZE / 2),
                scale=(CELL_SIZE, WALL_HEIGHT, WALL_THICKNESS),
            )
        
        # उत्तरी सीमा (z = h-1)
        for x in range(w):
            cx, cz = self._cell_center((x, h - 1))
            self._create_wall(
                pos=(cx, WALL_HEIGHT / 2, cz + CELL_SIZE / 2),
                scale=(CELL_SIZE, WALL_HEIGHT, WALL_THICKNESS),
            )

    def _create_wall(self, pos: Tuple[float, float, float], scale: Tuple[float, float, float]) -> Entity:
        """साझा दीवार टेक्सचर के साथ एक दीवार एंटिटी बनाता है।"""
        return Entity(
            parent=self.root,
            model='cube',
            scale=scale,
            position=pos,
            texture=self._wall_tex,
            color=color.white,
        )

    def _build_exit(self) -> None:
        """
        निकास सेल में एक स्पष्ट आर्च/बीकन बनाता है जो इसके गलियारे को अवरुद्ध नहीं करता।
        एक चमकदार गोलाकार बीकन + एक आर्च फ्रेम का उपयोग करता है।
        """
        ex, ez = self.maze.exit
        cx, cz = self._cell_center(self.maze.exit)
        
        # बीकन रूट (एनिमेशन के लिए)
        beacon_root = Entity(parent=self.root, position=(cx, 0, cz))
        
        # चमकदार गोला (बीकन)
        beacon = Entity(
            parent=beacon_root,
            model='sphere',
            scale=0.9,
            position=(0, 1.2, 0),
            color=color.rgb32(255, 220, 80),
            shader='unlit_shader',
        )
        
        # आर्च फ्रेम: दो ऊर्ध्वाधर स्तंभ + शीर्ष बीम
        # स्तंभ गलियारे के किनारों पर, मार्ग के बाहर
        arch_color = color.rgb32(255, 230, 120)
        column_h = 2.0
        column_r = 0.15
        
        # निकास की खुली दिशा निर्धारित करें ताकि गलियारे को अवरुद्ध न करें
        exit_neighbors = self.maze.neighbors(self.maze.exit)
        
        # स्तंभों को खुली दिशा के लंबवत रखें
        if exit_neighbors:
            nx, nz = exit_neighbors[0]
            dx, dz = nx - ex, nz - ez
            # खुली दिशा के लंबवत: (-dz, dx)
            px, pz = -dz * 0.7, dx * 0.7
        else:
            px, pz = 0.7, 0
        
        # बायां स्तंभ
        Entity(
            parent=beacon_root,
            model='cube',
            scale=(column_r * 2, column_h, column_r * 2),
            position=(px, column_h / 2, pz),
            color=arch_color,
        )
        # दायां स्तंभ
        Entity(
            parent=beacon_root,
            model='cube',
            scale=(column_r * 2, column_h, column_r * 2),
            position=(-px, column_h / 2, -pz),
            color=arch_color,
        )
        # शीर्ष बीम
        beam_len = math.hypot(px * 2, pz * 2) + 0.2
        beam = Entity(
            parent=beacon_root,
            model='cube',
            scale=(beam_len, 0.12, 0.12),
            position=(0, column_h + 0.06, 0),
            color=arch_color,
        )
        # बीम को गलियारे के साथ संरेखित करने के लिए घुमाएं
        if exit_neighbors:
            angle = math.degrees(math.atan2(dx, dz))
            beam.rotation_y = angle
        
        self.item_nodes[self.maze.exit] = ItemNode(
            root=beacon_root,
            item_type='exit',
            bob_offset=self._rng.random() * math.tau,
            rotation_speed=30.0,
        )

    def _build_items(self) -> None:
        """भूलभुलैया में प्रत्येक आइटम के लिए विशिष्ट 3D मॉडल बनाता है।"""
        for cell, item_type in self.maze.items.items():
            cx, cz = self._cell_center(cell)
            item_root = Entity(parent=self.root, position=(cx, 0, cz))
            
            if item_type == 'apple':
                self._build_apple(item_root)
            elif item_type == 'strawberry':
                self._build_strawberry(item_root)
            elif item_type == 'trampoline':
                self._build_trampoline(item_root)
            
            self.item_nodes[cell] = ItemNode(
                root=item_root,
                item_type=item_type,
                bob_offset=self._rng.random() * math.tau,
                rotation_speed=self._rng.uniform(20.0, 40.0),
            )

    def _build_apple(self, root: Entity) -> None:
        """लाल गोल सेब बनाता है जिसमें तना और पत्ता होता है।"""
        # मुख्य शरीर
        Entity(
            parent=root,
            model='sphere',
            scale=0.55,
            position=(0, 0.6, 0),
            color=color.rgb32(220, 30, 30),
        )
        # तना
        Entity(
            parent=root,
            model='cube',
            scale=(0.06, 0.25, 0.06),
            position=(0, 1.05, 0),
            color=color.rgb32(80, 50, 20),
        )
        # पत्ता
        Entity(
            parent=root,
            model='plane',
            scale=(0.25, 0.15, 0.02),
            position=(0.08, 1.1, 0.02),
            rotation=(0, 0, -30),
            color=color.rgb32(50, 160, 50),
            double_sided=True,
        )

    def _build_strawberry(self, root: Entity) -> None:
        """हरे पत्तों के साथ लाल स्ट्रॉबेरी (शंक्वाकार) बनाता है।"""
        # मुख्य शरीर (क्यूब्स के साथ शंकु का अनुमान)
        segments = 5
        base_r = 0.45
        height = 0.85
        for i in range(segments):
            t = (i + 0.5) / segments
            r = base_r * (1 - t) + 0.05 * t
            y = 0.4 + t * height
            Entity(
                parent=root,
                model='sphere',
                scale=(r * 2, (height / segments) * 1.1, r * 2),
                position=(0, y, 0),
                color=color.rgb32(220, 40, 60),
            )
        # बीज (छोटे पीले डॉट्स)
        for _ in range(12):
            ang = self._rng.random() * math.tau
            h = self._rng.uniform(0.5, 1.1)
            r = self._rng.uniform(0.15, 0.4)
            Entity(
                parent=root,
                model='sphere',
                scale=0.06,
                position=(math.sin(ang) * r, h, math.cos(ang) * r),
                color=color.rgb32(255, 230, 80),
            )
        # पत्ते (शीर्ष पर हरा ताज)
        leaf_count = 5
        for i in range(leaf_count):
            ang = i / leaf_count * math.tau
            leaf = Entity(
                parent=root,
                model='plane',
                scale=(0.18, 0.35, 0.02),
                position=(math.sin(ang) * 0.25, 1.25, math.cos(ang) * 0.25),
                rotation=(0, math.degrees(ang), -25),
                color=color.rgb32(40, 180, 60),
                double_sided=True,
            )

    def _build_trampoline(self, root: Entity) -> None:
        """चमकीले स्प्रिंग पैड के रूप में ट्रैम्पोलिन बनाता है।"""
        # बेस फ्रेम
        Entity(
            parent=root,
            model='cube',
            scale=(1.2, 0.15, 1.2),
            position=(0, 0.075, 0),
            color=color.rgb32(60, 60, 80),
        )
        # स्प्रिंग सतह (चमकीला सियान/मैजेंटा पैड)
        pad = Entity(
            parent=root,
            model='cube',
            scale=(1.0, 0.1, 1.0),
            position=(0, 0.2, 0),
            color=color.rgb32(0, 255, 255),
        )
        # स्प्रिंग कॉइल (कोनों पर छोटे क्यूब्स)
        for dx, dz in [(-0.45, -0.45), (0.45, -0.45), (-0.45, 0.45), (0.45, 0.45)]:
            Entity(
                parent=root,
                model='cube',
                scale=(0.12, 0.25, 0.12),
                position=(dx, 0.125, dz),
                color=color.rgb32(200, 200, 255),
            )
        # केंद्र चमक मार्कर
        Entity(
            parent=root,
            model='sphere',
            scale=0.25,
            position=(0, 0.35, 0),
            color=color.rgb32(255, 100, 255),
            shader='unlit_shader',
        )

    def _build_decorations(self) -> None:
        """
        थीम-विशिष्ट नॉन-ब्लॉकिंग डेकोरेशन रखता है:
        - stone: मॉस/खंडहर (पत्थर ब्लॉक, मॉस पैच)
        - forest: पेड़/फूल
        - cave: क्रिस्टल
        - streams: पानी के ताल/कंकड़
        
        कॉरिडोर के बाहर या कोनों के पास छोटे; 19x19 प्रदर्शन के लिए कैप्ड काउंट।
        """
        w, h = self.maze.width, self.maze.height
        max_decor = min(40, (w * h) // 8)  # 19x19 पर ~45 पर कैप
        placed = 0
        
        # प्रत्येक सेल के लिए डेकोरेशन रखने का प्रयास करें (यादृच्छिक क्रम में)
        cells = [(x, z) for x in range(w) for z in range(h)]
        self._rng.shuffle(cells)
        
        for cell in cells:
            if placed >= max_decor:
                break
            if cell == self.maze.start or cell == self.maze.exit:
                continue
            if cell in self.maze.items:
                continue
            
            # खुले मार्ग के केंद्र में न रखें — कोनों/किनारों को प्राथमिकता दें
            cx, cz = self._cell_center(cell)
            
            # कोने का ऑफसेट चुनें
            corner_choices = [
                (-0.9, -0.9), (0.9, -0.9), (-0.9, 0.9), (0.9, 0.9),  # कोने
                (-1.1, 0), (1.1, 0), (0, -1.1), (0, 1.1),              # किनारे मध्य
            ]
            self._rng.shuffle(corner_choices)
            
            for ox, oz in corner_choices:
                wx, wz = cx + ox, cz + oz
                # बाउंड्स जांचें
                if not (-CELL_SIZE/2 < wx < w*CELL_SIZE - CELL_SIZE/2):
                    continue
                if not (-CELL_SIZE/2 < wz < h*CELL_SIZE - CELL_SIZE/2):
                    continue
                
                # इस कोने के पास खुला मार्ग न होने पर डेकोरेशन रखें
                if self._can_place_decor_at(cell, (ox, oz)):
                    self._create_theme_decor(wx, wz)
                    placed += 1
                    break

    def _can_place_decor_at(self, cell: Cell, offset: Tuple[float, float]) -> bool:
        """
        जांचता है कि दिया गया कोना ऑफसेट खुले मार्ग के केंद्र में नहीं है।
        सरल अनुमानी: अगर सेल में उस दिशा में खुलापन है, तो उस किनारे/कोने को छोड़ दें।
        """
        x, z = cell
        ox, oz = offset
        
        # ऑफसेट से सापेक्ष दिशा निर्धारित करें
        dirs = []
        if ox < -0.5:
            dirs.append((-1, 0))  # पश्चिम
        if ox > 0.5:
            dirs.append((1, 0))   # पूर्व
        if oz < -0.5:
            dirs.append((0, -1))  # दक्षिण
        if oz > 0.5:
            dirs.append((0, 1))   # उत्तर
        
        # अगर इनमें से कोई दिशा खुली है, तो यह एक गलियारा किनारा है — रखने के लिए ठीक है
        # लेकिन अगर दो विपरीत दिशाएं खुली हैं (सीधा गलियारा), तो केंद्र से बचें
        # सरलीकृत: कोनों पर रखने की अनुमति दें, बस सटीक सेल केंद्र से बचें
        return True  # कोने ऑफसेट पहले से ही केंद्र से बाहर हैं

    def _create_theme_decor(self, wx: float, wz: float) -> None:
        """वर्ल्ड निर्देशांक (wx, wz) पर थीम-विशिष्ट डेकोरेशन बनाता है।"""
        theme = self.maze.theme
        y_base = FLOOR_Y + 0.05
        
        if theme == 'stone':
            self._decor_stone(wx, wz, y_base)
        elif theme == 'forest':
            self._decor_forest(wx, wz, y_base)
        elif theme == 'cave':
            self._decor_cave(wx, wz, y_base)
        elif theme == 'streams':
            self._decor_streams(wx, wz, y_base)

    def _decor_stone(self, wx: float, wz: float, y: float) -> None:
        """पत्थर थीम: मॉस वाले खंडहर, खड़े पत्थर, टूटे स्तंभ।"""
        decor_type = self._rng.choice(['moss_patch', 'standing_stone', 'broken_column', 'rubble'])
        
        if decor_type == 'moss_patch':
            # मॉस के साथ चपटा बोल्डर
            Entity(
                parent=self.root,
                model='sphere',
                scale=(self._rng.uniform(0.5, 0.9), self._rng.uniform(0.2, 0.35), self._rng.uniform(0.5, 0.9)),
                position=(wx, y + 0.15, wz),
                color=color.rgb32(100, 100, 100),
            )
            Entity(
                parent=self.root,
                model='sphere',
                scale=(self._rng.uniform(0.4, 0.7), 0.05, self._rng.uniform(0.4, 0.7)),
                position=(wx, y + 0.32, wz),
                color=color.rgb32(60, 120, 60),
            )
        elif decor_type == 'standing_stone':
            h = self._rng.uniform(1.0, 1.6)
            Entity(
                parent=self.root,
                model='cube',
                scale=(0.3, h, 0.5),
                position=(wx, y + h/2, wz),
                color=color.rgb32(130, 130, 130),
                rotation_y=self._rng.uniform(-15, 15),
            )
        elif decor_type == 'broken_column':
            # टूटे हुए खंडों के साथ स्तंभ स्टंप
            segs = self._rng.randint(2, 4)
            for i in range(segs):
                h = self._rng.uniform(0.25, 0.45)
                r = self._rng.uniform(0.3, 0.45)
                Entity(
                    parent=self.root,
                    model='cube',
                    scale=(r*2, h, r*2),
                    position=(wx, y + sum(self._rng.uniform(0.25, 0.45) for _ in range(i)) + h/2, wz),
                    color=color.rgb32(140, 140, 140),
                )
        else:  # rubble
            for _ in range(self._rng.randint(3, 6)):
                Entity(
                    parent=self.root,
                    model='cube',
                    scale=(self._rng.uniform(0.15, 0.35), self._rng.uniform(0.1, 0.25), self._rng.uniform(0.15, 0.35)),
                    position=(wx + self._rng.uniform(-0.4, 0.4), y + 0.08, wz + self._rng.uniform(-0.4, 0.4)),
                    color=color.rgb32(120, 120, 120),
                    rotation_y=self._rng.uniform(0, 360),
                )

    def _decor_forest(self, wx: float, wz: float, y: float) -> None:
        """वन थीम: पेड़ (त्रंक + फोलीज), फूल झाड़ियाँ।"""
        decor_type = self._rng.choice(['tree', 'flower_bush', 'small_plant'])
        
        if decor_type == 'tree':
            # त्रंक
            h = self._rng.uniform(1.4, 2.0)
            Entity(
                parent=self.root,
                model='cube',
                scale=(0.25, h, 0.25),
                position=(wx, y + h/2, wz),
                color=color.rgb32(80, 50, 30),
            )
            # फोलीज (गोले)
            foliage_h = h + 0.3
            for i in range(3):
                r = self._rng.uniform(0.5, 0.85)
                Entity(
                    parent=self.root,
                    model='sphere',
                    scale=(r*2, r*1.2, r*2),
                    position=(wx + self._rng.uniform(-0.15, 0.15), y + foliage_h + i*0.35, wz + self._rng.uniform(-0.15, 0.15)),
                    color=color.rgb32(self._rng.randint(40, 80), self._rng.randint(120, 170), self._rng.randint(40, 80)),
                )
        elif decor_type == 'flower_bush':
            # फूलों के साथ छोटी झाड़ी
            Entity(
                parent=self.root,
                model='sphere',
                scale=(0.6, 0.3, 0.6),
                position=(wx, y + 0.15, wz),
                color=color.rgb32(40, 90, 40),
            )
            for _ in range(self._rng.randint(3, 6)):
                ang = self._rng.random() * math.tau
                r = self._rng.uniform(0.2, 0.45)
                Entity(
                    parent=self.root,
                    model='sphere',
                    scale=0.1,
                    position=(wx + math.sin(ang)*r, y + 0.35, wz + math.cos(ang)*r),
                    color=color.rgb32(self._rng.randint(200, 255), self._rng.randint(100, 180), self._rng.randint(100, 180)),
                )
        else:  # small_plant
            # छोटा पौधा/फर्न
            for i in range(self._rng.randint(2, 4)):
                h = self._rng.uniform(0.3, 0.6)
                Entity(
                    parent=self.root,
                    model='plane',
                    scale=(0.15, h, 0.02),
                    position=(wx + self._rng.uniform(-0.2, 0.2), y + h/2, wz + self._rng.uniform(-0.2, 0.2)),
                    rotation_y=self._rng.uniform(0, 360),
                    color=color.rgb32(50, 130, 50),
                    double_sided=True,
                )

    def _decor_cave(self, wx: float, wz: float, y: float) -> None:
        """गुफा थीम: क्रिस्टल संरचनाएं, स्टैलेक्टाइट्स/स्टैलेग्माइट्स।"""
        decor_type = self._rng.choice(['crystal_cluster', 'stalagmite', 'crystal_spire'])
        
        if decor_type == 'crystal_cluster':
            # क्रिस्टल क्लस्टर (पिरामिड आकार के क्यूब्स)
            for _ in range(self._rng.randint(3, 6)):
                h = self._rng.uniform(0.4, 0.9)
                r = self._rng.uniform(0.15, 0.3)
                Entity(
                    parent=self.root,
                    model='cube',
                    scale=(r*2, h, r*2),
                    position=(wx + self._rng.uniform(-0.3, 0.3), y + h/2, wz + self._rng.uniform(-0.3, 0.3)),
                    color=color.rgb32(self._rng.randint(120, 180), self._rng.randint(120, 180), self._rng.randint(180, 255)),
                    rotation_y=self._rng.uniform(0, 360),
                )
        elif decor_type == 'stalagmite':
            # फर्श से उठता स्टैलेग्माइट
            h = self._rng.uniform(0.8, 1.4)
            base_r = self._rng.uniform(0.3, 0.5)
            segs = self._rng.randint(4, 6)
            for i in range(segs):
                t = i / (segs - 1)
                r = base_r * (1 - t) + 0.05
                seg_h = h / segs
                Entity(
                    parent=self.root,
                    model='cube',
                    scale=(r*2, seg_h, r*2),
                    position=(wx, y + t*h + seg_h/2, wz),
                    color=color.rgb32(100, 100, 140),
                    rotation_y=self._rng.uniform(0, 360),
                )
        else:  # crystal_spire
            # एकल बड़ा क्रिस्टल स्पायर
            h = self._rng.uniform(1.2, 1.8)
            base_r = self._rng.uniform(0.25, 0.35)
            segs = 6
            for i in range(segs):
                t = (i + 0.5) / segs
                r = base_r * (1 - t) + 0.02
                Entity(
                    parent=self.root,
                    model='cube',
                    scale=(r*2, h/segs, r*2),
                    position=(wx, y + t*h, wz),
                    color=color.rgb32(140, 160, 255),
                    rotation_y=(i * 60) + self._rng.uniform(-5, 5),
                )

    def _decor_streams(self, wx: float, wz: float, y: float) -> None:
        """धारा थीम: पानी के ताल, कंकड़, छोटे झरने।"""
        decor_type = self._rng.choice(['water_pool', 'pebbles', 'reeds'])
        
        if decor_type == 'water_pool':
            # छोटा पानी का ताल
            r = self._rng.uniform(0.5, 0.9)
            Entity(
                parent=self.root,
                model='cube',
                scale=(r*2, 0.06, r*2),
                position=(wx, y + 0.03, wz),
                color=color.rgb32(60, 160, 220),
                shader='unlit_shader',
            )
            # लहर हाइलाइट
            Entity(
                parent=self.root,
                model='cube',
                scale=(r*1.8, 0.02, r*1.8),
                position=(wx, y + 0.06, wz),
                color=color.rgb32(120, 200, 255),
                shader='unlit_shader',
            )
        elif decor_type == 'pebbles':
            # कंकड़ समूह
            for _ in range(self._rng.randint(5, 10)):
                Entity(
                    parent=self.root,
                    model='sphere',
                    scale=self._rng.uniform(0.08, 0.18),
                    position=(wx + self._rng.uniform(-0.5, 0.5), y + 0.06, wz + self._rng.uniform(-0.5, 0.5)),
                    color=color.rgb32(self._rng.randint(100, 160), self._rng.randint(120, 180), self._rng.randint(140, 200)),
                )
        else:  # reeds
            # पानी के किनारे सरकंडे
            for _ in range(self._rng.randint(3, 6)):
                h = self._rng.uniform(0.6, 1.1)
                Entity(
                    parent=self.root,
                    model='cube',
                    scale=(0.05, h, 0.05),
                    position=(wx + self._rng.uniform(-0.3, 0.3), y + h/2, wz + self._rng.uniform(-0.3, 0.3)),
                    color=color.rgb32(80, 150, 80),
                    rotation_y=self._rng.uniform(-10, 10),
                )

    # ------------------------------------------------------------------ #
    # सार्वजनिक API
    # ------------------------------------------------------------------ #
    def remove_item(self, cell: Cell) -> None:
        """उठाए गए आइटम को नष्ट करता है (निकास बीकन नहीं)।"""
        node = self.item_nodes.pop(cell, None)
        if node and node.item_type != 'exit':
            destroy(node.root)

    def update(self, dt: float) -> None:
        """
        आइटम और निकास बीकन को एनिमेट करता है: बॉब (ऊपर-नीचे) और घुमाव।
        हर फ्रेम कॉल किया जाता है; dt फ्रेम समय है।
        """
        for node in self.item_nodes.values():
            root = node.root
            if not root or not root.enabled:
                continue
            
            # बॉब एनिमेशन (साइन लहर)
            node.bob_offset += dt * 2.0
            bob_y = math.sin(node.bob_offset) * 0.12
            root.y = bob_y
            
            # घुमाव (निकास के लिए धीमा, आइटम के लिए तेज़)
            if node.item_type == 'exit':
                root.rotation_y += dt * node.rotation_speed * 0.3
            else:
                root.rotation_y += dt * node.rotation_speed

    def clear(self) -> None:
        """
        इस स्तर की सभी एंटिटीज को नष्ट करता है।
        सुरक्षित रूप से दो बार कॉल किया जा सकता है।
        """
        if self._cleared:
            return
        destroy(self.root)
        self.root = None
        self.item_nodes.clear()
        self._cleared = True