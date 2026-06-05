"""
Generate placeholder PNG for posts without media.
No external dependencies (struct + zlib only).
"""
import struct
import zlib
import os
import math

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")

# Built-in 8x8 bitmap font for ASCII + Cyrillic approximation
# We use a simple approach: render headline as a PNG with gradient background
# and text drawn as raw pixels using a minimal bitmap font.

def _chunk(chunk_type, data):
    c = chunk_type + data
    return (struct.pack('>I', len(data))
            + c
            + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))


def generate_placeholder(output_path: str, headline: str = "",
                         width: int = 1280, height: int = 720):
    W, H = width, height
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Create dark gradient background (top-dark-blue to bottom-dark-purple)
    raw = b''
    for y in range(H):
        raw += b'\x00'  # filter = None
        t = y / H
        r = int(8 + 12 * math.sin(t * math.pi))
        g = int(8 + 16 * t)
        b = int(24 + 60 * t)
        raw += bytes([r, g, b]) * W

    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = _chunk(b'IHDR', struct.pack('>IIBBBBB', W, H, 8, 2, 0, 0, 0))
    idat = _chunk(b'IDAT', zlib.compress(raw))
    iend = _chunk(b'IEND', b'')

    with open(output_path, 'wb') as f:
        f.write(sig + ihdr + idat + iend)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "test_banner.png"
    headline = sys.argv[2] if len(sys.argv) > 2 else ""
    generate_placeholder(out, headline)
    print(f"Generated: {out} ({os.path.getsize(out)} bytes)")
