"""
YOLO Dataset Initializer for SmartSpace AI
Creates the standardized directory structure and generates data.yaml
with the 10 interior object target classes.
"""
import os
import argparse
import sys

# Add parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from config import TARGET_CLASSES

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

DATA_YAML_TEMPLATE = """# SmartSpace AI - Interior Object Detection Dataset
# 10 Specialized Interior Object Classes

path: .
train: images/train
val: images/val
test: images/test

# Classes
names:
{names_yaml}
"""

def setup_yolo_dataset(base_dir: str = "data/yolo_dataset"):
    """
    Creates train/val/test folders for images and labels,
    and writes data.yaml matching the SmartSpace AI specification.
    """
    abs_base = base_dir if os.path.isabs(base_dir) else os.path.join(PROJECT_ROOT, base_dir)
    print(f"Setting up SmartSpace AI YOLO dataset at: {abs_base}")
    
    subdirs = [
        "images/train", "images/val", "images/test",
        "labels/train", "labels/val", "labels/test"
    ]
    
    for sub in subdirs:
        folder = os.path.join(abs_base, sub)
        os.makedirs(folder, exist_ok=True)
        print(f"  [+] Created directory: {folder}")
        
    # Format names yaml
    names_str = "\n".join([f"  {idx}: {name}" for idx, name in enumerate(TARGET_CLASSES)])
    yaml_content = DATA_YAML_TEMPLATE.format(names_yaml=names_str)
    
    yaml_path = os.path.join(abs_base, "data.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
        
    print(f"\n[SUCCESS] data.yaml successfully generated at: {yaml_path}")
    print("\n--- data.yaml Contents ---")
    print(yaml_content)
    return yaml_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create YOLO dataset folder structure and data.yaml")
    parser.add_argument("--path", type=str, default="data/yolo_dataset", help="Target dataset root path")
    args = parser.parse_args()
    
    setup_yolo_dataset(args.path)
