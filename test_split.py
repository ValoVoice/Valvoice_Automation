import sys
import os

# Add current directory to path so we can import from main.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock out modules that cause DLL load failures
from unittest.mock import MagicMock
sys.modules['google.generativeai'] = MagicMock()
sys.modules['edge_tts'] = MagicMock()

from main import apply_ab_split
import settings

def test_ab_split():
    print("Testing apply_ab_split...")
    # Mock data
    scenes = [
        {"scene_number": "1", "visual_search": "test 1", "duration_seconds": 3.0}, # Short
        {"scene_number": "2", "visual_search": "test 2", "duration_seconds": 6.0}, # Long
        {"scene_number": "3", "visual_search": "test 3", "duration_seconds": 2.0}, # Short
    ]
    measured_durations = [3.0, 6.0, 2.0]
    
    settings.MAX_SCENE_DURATION_BEFORE_SPLIT = 4.0
    
    render_scenes, render_durations = apply_ab_split(scenes, measured_durations)
    
    assert len(render_scenes) == 4, f"Expected 4 scenes, got {len(render_scenes)}"
    assert len(render_durations) == 4, f"Expected 4 durations, got {len(render_durations)}"
    
    print("Test passed! A/B splitting correctly splits scenes and doubles the elements.")
    print(f"Resulting scenes: {[s['scene_number'] for s in render_scenes]}")
    print(f"Resulting durations: {render_durations}")

if __name__ == "__main__":
    test_ab_split()
