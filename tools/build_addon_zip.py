#!/usr/bin/env python3
"""Build a Kodi-compatible addon ZIP from the repository root.

Usage: python tools/build_addon_zip.py
Output: dist/plugin.program.simple.favourites-0.1.33.7a.zip
"""
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ADDON_XML = ROOT / "addon.xml"
DIST = ROOT / "dist"


def main():
    addon = ET.parse(ADDON_XML).getroot()
    addon_id = addon.attrib["id"]
    version = addon.attrib["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:~(?:alpha|beta)\d*)?", version):
        raise SystemExit("Invalid Kodi version: %s (use x.y.z or x.y.z~alpha/beta)" % version)

    files = []
    ignored = {".git", ".github", "dist", "__pycache__"}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored for part in path.parts):
            continue
        files.append(path)

    DIST.mkdir(exist_ok=True)
    output = DIST / ("%s-%s.zip" % (addon_id, version))
    if output.exists():
        output.unlink()

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(files):
            relative = path.relative_to(ROOT).as_posix()
            zf.write(path, "%s/%s" % (addon_id, relative))

    print(output)


if __name__ == "__main__":
    main()
