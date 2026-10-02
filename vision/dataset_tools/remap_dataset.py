"""
Dataset Remapping Utility for SmartSpace AI
Remaps public datasets (Kaggle Architecture, Kaggle Indoor Objects, COCO, Roboflow)
to the project's standard 10-class taxonomy:
  0: bed, 1: sofa, 2: chair, 3: table, 4: wardrobe,
  5: desk, 6: tv, 7: cabinet, 8: door, 9: window
"""
import os
import glob
import shutil
import argparse
import sys
from typing import Dict, List, Optional

# Add parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from config import TARGET_CLASSES, CLASS_TO_IDX

# Comprehensive dictionary mapping common aliases in COCO, Kaggle, Roboflow to target classes
CLASS_SYNONYMS = {
    # 0: bed
    "bed": 0, "double_bed": 0, "single_bed": 0, "bunk_bed": 0, "queen_bed": 0, "king_bed": 0,
    # 1: sofa
    "sofa": 1, "couch": 1, "armchair": 1, "sectional": 1, "lounge": 1, "settee": 1,
    # 2: chair
    "chair": 2, "stool": 2, "office_chair": 2, "dining_chair": 2, "seat": 2,
    # 3: table
    "table": 3, "dining_table": 3, "coffee_table": 3, "side_table": 3, "nightstand": 3,
    # 4: wardrobe
    "wardrobe": 4, "closet": 4, "cupboard": 4, "armoire": 4,
    # 5: desk
    "desk": 5, "study_desk": 5, "workstation": 5, "computer_desk": 5,
    # 6: tv
    "tv": 6, "television": 6, "monitor": 6, "screen": 6, "tv_monitor": 6,
    # 7: cabinet
    "cabinet": 7, "sideboard": 7, "drawer": 7, "chest_of_drawers": 7, "dresser": 7, "credenza": 7,
    # 8: door
    "door": 8, "interior_door": 8, "wooden_door": 8, "entrance": 8,
    # 9: window
    "window": 9, "glass_window": 9, "curtain_window": 9, "vent": 9
}

# Standard COCO 80-class mapping to SmartSpace AI 10-class subset
COCO_CLASS_MAP = {
    56: 2,  # chair -> 2
    57: 1,  # couch -> 1
    59: 0,  # bed -> 0
    60: 3,  # dining table -> 3
    62: 6   # tv -> 6
}

def remap_yolo_txt_files(src_labels_dir: str, dst_labels_dir: str, 
                         mapping: Dict[int, int], filter_unmapped: bool = True):
    """
    Reads YOLO format label files from src_labels_dir, maps class IDs according
    to the mapping dictionary, and writes updated files to dst_labels_dir.
    """
    os.makedirs(dst_labels_dir, exist_ok=True)
    label_files = glob.glob(os.path.join(src_labels_dir, "*.txt"))
    print(f"Found {len(label_files)} label files in: {src_labels_dir}")
    
    total_boxes = 0
    mapped_boxes = 0
    
    for l_path in label_files:
        filename = os.path.basename(l_path)
        dst_path = os.path.join(dst_labels_dir, filename)
        
        valid_lines = []
        with open(l_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    total_boxes += 1
                    src_cls = int(parts[0])
                    if src_cls in mapping:
                        new_cls = mapping[src_cls]
                        valid_lines.append(f"{new_cls} {' '.join(parts[1:5])}\n")
                        mapped_boxes += 1
                    elif not filter_unmapped:
                        valid_lines.append(line)
                        
        if valid_lines:
            with open(dst_path, "w", encoding="utf-8") as f:
                f.writelines(valid_lines)
                
    print(f"Remapping complete. Processed {total_boxes} boxes, successfully mapped {mapped_boxes} into target classes.")

def generate_mapping_from_names(source_class_names: List[str]) -> Dict[int, int]:
    """Generates an index-to-index mapping from a list of original source class names."""
    mapping = {}
    for src_idx, name in enumerate(source_class_names):
        clean_name = name.lower().strip().replace(" ", "_").replace("-", "_")
        if clean_name in CLASS_SYNONYMS:
            target_idx = CLASS_SYNONYMS[clean_name]
            mapping[src_idx] = target_idx
            print(f"  [Map] Source ID {src_idx} ('{name}') -> Target ID {target_idx} ('{TARGET_CLASSES[target_idx]}')")
        else:
            print(f"  [Skip] Source ID {src_idx} ('{name}') does not match any of the 10 target classes")
    return mapping

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Remap YOLO dataset classes to SmartSpace 10-class standard")
    parser.add_argument("--src-labels", type=str, required=False, default="data/raw_labels", help="Source labels folder")
    parser.add_argument("--dst-labels", type=str, required=False, default="data/yolo_dataset/labels/train", help="Destination labels folder")
    args = parser.parse_args()
    
    print("=== SmartSpace AI Dataset Remapping Utility ===")
    print("Target Classes:")
    for idx, c in enumerate(TARGET_CLASSES):
        print(f"  {idx}: {c}")
    print("\nTo remap an external dataset, call this script with source and destination label directories.")
