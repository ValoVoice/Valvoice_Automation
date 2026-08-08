import os
import random
import config

ASSET_DIRS = {
    "valvoice_demo": os.path.join(config.PROJECT_ROOT, "assets", "valvoice"),
    "gameplay": os.path.join(config.PROJECT_ROOT, "assets", "gameplay"),
    "screenshot": os.path.join(config.PROJECT_ROOT, "assets", "screenshots"),
    "ui": os.path.join(config.PROJECT_ROOT, "assets", "ui"),
}

def get_random_asset(tag: str) -> str:
    """
    Given an asset tag, return a random absolute file path from the corresponding local directory.
    Raises ValueError if no files exist.
    """
    if tag not in ASSET_DIRS:
        raise ValueError(f"Unknown asset tag requested: {tag}")
        
    directory = ASSET_DIRS[tag]
    if not os.path.exists(directory):
        raise FileNotFoundError(f"Asset directory does not exist: {directory}")
        
    valid_extensions = ('.mp4', '.mov', '.png', '.jpg', '.jpeg', '.webm')
    files = [
        f for f in os.listdir(directory)
        if f.lower().endswith(valid_extensions)
    ]
    
    if not files:
        raise ValueError(f"No valid assets found in {directory} for tag '{tag}'")
        
    selected = random.choice(files)
    return os.path.join(directory, selected)

def select_assets_for_script(script: dict) -> dict:
    """
    Takes a generated script and adds a 'selected_asset' path to each scene
    based on the first item in 'required_visuals'.
    """
    scenes = script.get("scenes", [])
    if not scenes:
        raise ValueError("Cannot select assets: script has no scenes")
        
    for scene in scenes:
        visuals = scene.get("required_visuals", [])
        if not visuals:
            raise ValueError(f"Scene {scene.get('scene_number', '?')} has no required_visuals")
            
        # For V1, we simply map the first required visual tag to a local file
        tag = visuals[0]
        try:
            asset_path = get_random_asset(tag)
            scene["selected_asset"] = asset_path
            print(f"  ✓ Mapped {tag} -> {os.path.basename(asset_path)}")
        except Exception as e:
            raise RuntimeError(f"Asset selection failed for scene {scene.get('scene_number', '?')}: {e}")
            
    return script
