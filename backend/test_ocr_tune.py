"""Tune preprocessing: try grayscale + contrast + sharpen + different PSM."""
import sys
sys.path.insert(0, ".")
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import pytesseract

base = Image.open("data/test_redact_out/dni.jpg")
print("Original size:", base.size)
scale = 4.0
up = base.resize((int(base.size[0] * scale), int(base.size[1] * scale)), Image.BICUBIC)

variants = {
    "a_lanczos": base.resize((int(base.size[0] * 6.74), int(base.size[1] * 6.74)), Image.LANCZOS),
    "b_bicubic": up,
    "c_bicubic_gray": ImageOps.grayscale(up),
    "d_bicubic_gray_contrast": ImageEnhance.Contrast(ImageOps.grayscale(up)).enhance(1.8),
    "e_bicubic_gray_contrast_sharp": ImageEnhance.Contrast(ImageOps.grayscale(up)).enhance(1.8).filter(ImageFilter.SHARPEN),
    "f_bicubic_autocontrast": ImageOps.autocontrast(up),
    "g_bicubic_autocontrast_gray_sharp": ImageOps.autocontrast(ImageOps.grayscale(up)).filter(ImageFilter.SHARPEN),
}

configs = ["--psm 6", "--psm 11", "--psm 12"]

for vname, img in variants.items():
    print(f"\n\n=========== variant: {vname} (mode={img.mode}, size={img.size}) ===========")
    for cfg in configs:
        text = pytesseract.image_to_string(img, lang="spa+eng", config=cfg)
        clean = text.strip()
        # Print a summary: chars extracted and the content
        print(f"\n  --- {cfg} ({len(clean)} chars) ---")
        # Only show lines that have digits or likely PII (to avoid noise)
        for line in clean.split("\n"):
            ls = line.strip()
            if ls:
                print(f"    {ls!r}")
