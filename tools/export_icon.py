import os
import sys
from pathlib import Path

try:
    # ensure repo root is on path
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from main import create_image
    from PIL import Image

    out_root = repo_root
    out_output = repo_root / 'Output'
    out_output.mkdir(parents=True, exist_ok=True)

    img = create_image()
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # Save a large PNG and an ICO containing multiple sizes
    png_path = out_root / 'lightguard_logo.png'
    ico_path_root = out_root / 'lightguard_logo.ico'
    ico_path_output = out_output / 'lightguard_logo.ico'

    # PNG at 256x256
    try:
        png = img.resize((256, 256), Image.LANCZOS)
        png.save(png_path, format='PNG')
        print('Saved', png_path)
    except Exception as e:
        print('PNG save failed:', e)

    # ICO with several sizes
    try:
        sizes = [(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)]
        # Pillow supports saving ICO with sizes parameter
        img.save(ico_path_root, format='ICO', sizes=sizes)
        print('Saved', ico_path_root)
        # also copy into Output for installer convenience
        img.save(ico_path_output, format='ICO', sizes=sizes)
        print('Saved', ico_path_output)
    except Exception as e:
        print('ICO save failed:', e)

except Exception as e:
    print('export_icon failed:', e)
    raise
