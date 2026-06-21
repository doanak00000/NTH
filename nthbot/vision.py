"""
Nhận diện hình ảnh bằng OpenCV (template matching).

Ý tưởng: chụp màn hình -> tìm ảnh mẫu (nút/icon/NPC) trong đó.
Nếu khớp >= ngưỡng confidence thì trả về tâm vùng khớp để tap vào.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import cv2
import numpy as np


def imread_unicode(path: str):
    """cv2.imread an toàn với đường dẫn tiếng Việt/Unicode trên Windows."""
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def imwrite_unicode(path: str, img: np.ndarray) -> bool:
    """cv2.imwrite an toàn với đường dẫn tiếng Việt/Unicode trên Windows."""
    ext = os.path.splitext(path)[1] or ".png"
    ok, buf = cv2.imencode(ext, img)
    if ok:
        buf.tofile(path)
    return bool(ok)


@dataclass
class Match:
    found: bool
    x: int = 0          # tâm theo trục X
    y: int = 0          # tâm theo trục Y
    confidence: float = 0.0
    width: int = 0
    height: int = 0

    def __bool__(self):
        return self.found


class TemplateStore:
    """Nạp & cache ảnh mẫu từ thư mục templates."""

    def __init__(self, templates_dir: str):
        self.dir = templates_dir
        self._cache: dict[str, np.ndarray] = {}

    def get(self, name: str) -> np.ndarray:
        if name in self._cache:
            return self._cache[name]
        path = name if os.path.isabs(name) else os.path.join(self.dir, name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Không thấy ảnh mẫu: {path}")
        img = imread_unicode(path)
        if img is None:
            raise ValueError(f"Đọc ảnh mẫu thất bại: {path}")
        self._cache[name] = img
        return img


def find_template(
    screen: np.ndarray,
    template: np.ndarray,
    confidence: float = 0.85,
    region: tuple[int, int, int, int] | None = None,
    multi_scale: bool = False,
) -> Match:
    """Tìm template trong screen.

    region: (x, y, w, h) giới hạn vùng tìm để nhanh & chính xác hơn (tuỳ chọn).
    multi_scale: thử nhiều tỉ lệ khi độ phân giải mẫu khác với máy.
    """
    offset_x, offset_y = 0, 0
    search = screen
    if region:
        rx, ry, rw, rh = region
        search = screen[ry:ry + rh, rx:rx + rw]
        offset_x, offset_y = rx, ry

    scales = [1.0]
    if multi_scale:
        scales = [0.8, 0.9, 1.0, 1.1, 1.25]

    best = Match(found=False)
    for scale in scales:
        if scale != 1.0:
            tmpl = cv2.resize(template, None, fx=scale, fy=scale)
        else:
            tmpl = template
        th, tw = tmpl.shape[:2]
        if tmpl.shape[0] > search.shape[0] or tmpl.shape[1] > search.shape[1]:
            continue
        res = cv2.matchTemplate(search, tmpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val > best.confidence:
            best = Match(
                found=max_val >= confidence,
                x=offset_x + max_loc[0] + tw // 2,
                y=offset_y + max_loc[1] + th // 2,
                confidence=float(max_val),
                width=tw,
                height=th,
            )
            if best.found and not multi_scale:
                break
    return best


# ---- OCR (tuỳ chọn, cần cài Tesseract + pytesseract) --------------------
def ocr_text(screen: np.ndarray, region: tuple[int, int, int, int] | None = None) -> str:
    try:
        import pytesseract
    except ImportError:
        raise RuntimeError("OCR cần: pip install pytesseract + cài Tesseract-OCR.")
    img = screen
    if region:
        x, y, w, h = region
        img = screen[y:y + h, x:x + w]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return pytesseract.image_to_string(gray).strip()
