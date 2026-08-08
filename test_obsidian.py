import os
import sys
from main import write_obsidian_frontmatter

script = {"title": "Test Title", "scenes": []}
metadata = {"youtube": {"title": "Test Title"}}
path = write_obsidian_frontmatter("VV_Test_001", "Test Topic", script, metadata, "C:/test/video.mp4", "PASS")
print(f"Generated: {path}")
print("---FILE CONTENT---")
with open(path, "r", encoding="utf-8") as f:
    print(f.read())
