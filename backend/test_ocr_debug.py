"""Debug: print raw OCR output on the DNI image so we can tune regex."""
import sys
sys.path.insert(0, ".")
from PIL import Image
import pytesseract

img = Image.open("data/test_redact_out/dni.jpg")
print("Original size:", img.size)
short = min(img.size)
if short < 1200:
    scale = max(2.0, 1200 / short)
    img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)), Image.LANCZOS)
    print("Upscaled to:", img.size, "scale=", round(scale, 2))

print("\n=== OCR plain text ===")
text = pytesseract.image_to_string(img, lang="spa+eng")
print(text)

print("\n=== Words with bounding boxes (conf > 30) ===")
data = pytesseract.image_to_data(img, lang="spa+eng", output_type=pytesseract.Output.DICT)
for i, word in enumerate(data["text"]):
    if word.strip():
        conf = int(data["conf"][i]) if data["conf"][i] != "-1" else -1
        if conf > 30:
            box = (data["left"][i], data["top"][i], data["width"][i], data["height"][i])
            print(f"  {word!r:30s} conf={conf:3d} box={box}")
