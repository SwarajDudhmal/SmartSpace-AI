"""
Synthetic Interior Dataset Generator for SmartSpace AI
Generates realistic schematic/perspective room images and matching normalized YOLO labels
for the 10 classes:
  0: bed, 1: sofa, 2: chair, 3: table, 4: wardrobe,
  5: desk, 6: tv, 7: cabinet, 8: door, 9: window

Outputs matching:
  images/{train,val,test}/room_XXXX.jpg
  labels/{train,val,test}/room_XXXX.txt (format: class_id cx cy w h)
"""
import os
import random
import argparse
import sys
from typing import List, Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageFont

# Add parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from config import TARGET_CLASSES, CLASS_TO_IDX

# Visual rendering styles for the 10 furniture classes
ITEM_STYLES = {
    0: {"name": "bed", "fill": (70, 130, 220), "border": (30, 70, 160), "detail": "pillows"},
    1: {"name": "sofa", "fill": (140, 90, 210), "border": (90, 50, 150), "detail": "cushions"},
    2: {"name": "chair", "fill": (20, 180, 200), "border": (10, 120, 140), "detail": "backrest"},
    3: {"name": "table", "fill": (40, 180, 120), "border": (20, 120, 75), "detail": "wood"},
    4: {"name": "wardrobe", "fill": (230, 150, 30), "border": (170, 100, 15), "detail": "doors"},
    5: {"name": "desk", "fill": (100, 105, 225), "border": (60, 65, 170), "detail": "laptop"},
    6: {"name": "tv", "fill": (225, 60, 140), "border": (160, 30, 90), "detail": "screen"},
    7: {"name": "cabinet", "fill": (240, 120, 40), "border": (180, 75, 20), "detail": "drawers"},
    8: {"name": "door", "fill": (230, 70, 70), "border": (180, 30, 30), "detail": "swing"},
    9: {"name": "window", "fill": (30, 180, 170), "border": (15, 120, 115), "detail": "glazing"}
}

def draw_wood_floor(draw: ImageDraw.ImageDraw, w: int, h: int, plank_h: int = 24):
    """Draws a subtle wooden plank texture."""
    base_color = (238, 230, 215)
    line_color = (220, 210, 195)
    for y in range(0, h, plank_h):
        draw.line([(0, y), (w, y)], fill=line_color, width=1)
        offset = (y // plank_h) % 2 * 60
        for x in range(offset, w, 120):
            draw.line([(x, y), (x, y + plank_h)], fill=line_color, width=1)

def generate_room_sample(img_w: int = 640, img_h: int = 640) -> Tuple[Image.Image, List[Tuple[int, float, float, float, float]]]:
    """
    Generates a single room image with furniture items and returns:
    (PIL.Image, list of [class_id, norm_cx, norm_cy, norm_w, norm_h])
    """
    img = Image.new("RGB", (img_w, img_h), (245, 240, 230))
    draw = ImageDraw.Draw(img)
    
    # 1. Flooring
    draw_wood_floor(draw, img_w, img_h)
    
    # 2. Room Walls & Baseboard
    wall_thick = 20
    draw.rectangle([0, 0, img_w, wall_thick], fill=(80, 85, 95))
    draw.rectangle([0, img_h - wall_thick, img_w, img_h], fill=(80, 85, 95))
    draw.rectangle([0, 0, wall_thick, img_h], fill=(80, 85, 95))
    draw.rectangle([img_w - wall_thick, 0, img_w, img_h], fill=(80, 85, 95))
    
    annotations = []
    
    # 3. Add Architectural Elements (Door & Window)
    # Door (Class 8)
    door_w, door_h = 45, wall_thick + 10
    door_x = random.randint(wall_thick + 20, img_w - wall_thick - 100)
    draw.rectangle([door_x, img_h - door_h, door_x + door_w, img_h], fill=(220, 60, 60), outline=(160, 20, 20), width=2)
    # Swing arc
    draw.arc([door_x - door_w, img_h - door_h - door_w, door_x + door_w, img_h - wall_thick], 270, 360, fill=(200, 50, 50), width=1)
    
    cx = (door_x + door_w / 2.0) / img_w
    cy = (img_h - door_h / 2.0) / img_h
    annotations.append((8, cx, cy, door_w / img_w, door_h / img_h))
    
    # Window (Class 9)
    win_w, win_h = 75, wall_thick + 6
    win_x = random.randint(wall_thick + 20, img_w - wall_thick - 120)
    draw.rectangle([win_x, 0, win_x + win_w, win_h], fill=(50, 200, 220), outline=(20, 130, 150), width=2)
    cx = (win_x + win_w / 2.0) / img_w
    cy = (win_h / 2.0) / img_h
    annotations.append((9, cx, cy, win_w / img_w, win_h / img_h))
    
    # 4. Furniture candidate selection
    room_theme = random.choice(["bedroom", "living_room", "study"])
    if room_theme == "bedroom":
        items_to_place = [0, 4, 5, 2] # bed, wardrobe, desk, chair
        if random.random() < 0.6: items_to_place.append(7) # cabinet
        if random.random() < 0.5: items_to_place.append(6) # tv
    elif room_theme == "living_room":
        items_to_place = [1, 3, 6, 2] # sofa, table, tv, chair
        if random.random() < 0.7: items_to_place.append(2) # second chair
        if random.random() < 0.6: items_to_place.append(7) # cabinet
    else:
        items_to_place = [5, 2, 7, 3] # desk, chair, cabinet, table
        if random.random() < 0.5: items_to_place.append(1) # sofa
        
    placed_boxes = []
    
    for cls_id in items_to_place:
        style = ITEM_STYLES[cls_id]
        
        # Dimensions based on class
        if cls_id == 0:   # bed
            box_w, box_h = random.randint(120, 150), random.randint(150, 180)
        elif cls_id == 1: # sofa
            box_w, box_h = random.randint(150, 190), random.randint(70, 90)
        elif cls_id == 2: # chair
            box_w, box_h = random.randint(45, 55), random.randint(45, 55)
        elif cls_id == 3: # table
            box_w, box_h = random.randint(90, 120), random.randint(60, 80)
        elif cls_id == 4: # wardrobe
            box_w, box_h = random.randint(110, 140), random.randint(45, 60)
        elif cls_id == 5: # desk
            box_w, box_h = random.randint(100, 130), random.randint(55, 70)
        elif cls_id == 6: # tv
            box_w, box_h = random.randint(90, 120), random.randint(15, 25)
        else:             # cabinet
            box_w, box_h = random.randint(70, 95), random.randint(35, 50)
            
        # Try to find a non-overlapping spot
        placed = False
        for _ in range(30):
            bx = random.randint(wall_thick + 10, img_w - wall_thick - box_w - 10)
            by = random.randint(wall_thick + 10, img_h - wall_thick - box_h - 10)
            
            # Check overlap with existing placed items
            overlap = False
            for (ox, oy, ow, oh) in placed_boxes:
                if not (bx + box_w + 10 < ox or bx > ox + ow + 10 or 
                        by + box_h + 10 < oy or by > oy + oh + 10):
                    overlap = True
                    break
                    
            if not overlap:
                placed = True
                placed_boxes.append((bx, by, box_w, box_h))
                
                # Draw subtle drop shadow
                draw.rectangle([bx + 4, by + 4, bx + box_w + 4, by + box_h + 4], fill=(210, 205, 195))
                # Draw main body
                draw.rectangle([bx, by, bx + box_w, by + box_h], fill=style["fill"], outline=style["border"], width=2)
                
                # Draw decorative interior details
                if style["detail"] == "pillows":
                    draw.rectangle([bx + 10, by + 10, bx + box_w/2 - 5, by + 35], fill=(240, 245, 255), outline=style["border"])
                    draw.rectangle([bx + box_w/2 + 5, by + 10, bx + box_w - 10, by + 35], fill=(240, 245, 255), outline=style["border"])
                elif style["detail"] == "cushions":
                    draw.line([(bx + box_w/3, by), (bx + box_w/3, by + box_h)], fill=style["border"], width=1)
                    draw.line([(bx + 2*box_w/3, by), (bx + 2*box_w/3, by + box_h)], fill=style["border"], width=1)
                elif style["detail"] == "laptop":
                    lw, lh = 30, 22
                    draw.rectangle([bx + (box_w-lw)/2, by + (box_h-lh)/2, bx + (box_w+lw)/2, by + (box_h+lh)/2], fill=(200, 205, 215))
                elif style["detail"] == "drawers":
                    draw.line([(bx, by + box_h/2), (bx + box_w, by + box_h/2)], fill=style["border"], width=1)
                    
                # Save YOLO normalized coordinates
                norm_cx = (bx + box_w / 2.0) / img_w
                norm_cy = (by + box_h / 2.0) / img_h
                norm_w = box_w / img_w
                norm_h = box_h / img_h
                annotations.append((cls_id, norm_cx, norm_cy, norm_w, norm_h))
                break
                
    return img, annotations

def generate_synthetic_dataset(output_dir: str = "data/yolo_dataset", 
                               train_count: int = 30, val_count: int = 8, test_count: int = 6):
    """
    Generates synthetic dataset split across train, val, and test.
    """
    splits = {
        "train": train_count,
        "val": val_count,
        "test": test_count
    }
    
    total_imgs = sum(splits.values())
    print(f"=== Generating Synthetic Interior YOLO Dataset ({total_imgs} images) ===")
    
    for split_name, count in splits.items():
        img_dir = os.path.join(output_dir, "images", split_name)
        lbl_dir = os.path.join(output_dir, "labels", split_name)
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(lbl_dir, exist_ok=True)
        
        print(f"Generating {count} images for split: {split_name}...")
        for i in range(1, count + 1):
            file_stem = f"room_{split_name}_{i:04d}"
            img, annots = generate_room_sample()
            
            # Save Image
            img_path = os.path.join(img_dir, f"{file_stem}.jpg")
            img.save(img_path, quality=92)
            
            # Save YOLO txt label
            lbl_path = os.path.join(lbl_dir, f"{file_stem}.txt")
            with open(lbl_path, "w") as f:
                for cls_id, cx, cy, w, h in annots:
                    f.write(f"{cls_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
                    
    print("\n[SUCCESS] Synthetic dataset generated successfully!")
    print(f"Images: {os.path.abspath(output_dir)}/images")
    print(f"Labels: {os.path.abspath(output_dir)}/labels")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic interior YOLO training data")
    parser.add_argument("--output", type=str, default="data/yolo_dataset", help="Output directory")
    parser.add_argument("--train", type=int, default=25, help="Train count")
    parser.add_argument("--val", type=int, default=6, help="Val count")
    parser.add_argument("--test", type=int, default=5, help="Test count")
    args = parser.parse_args()
    
    generate_synthetic_dataset(args.output, args.train, args.val, args.test)
