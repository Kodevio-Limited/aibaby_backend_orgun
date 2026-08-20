"""Outfit editing (local, deterministic).

When a user changes the outfit on an already-generated baby image we do NOT
send the image back through the generative model — that drifted the face. Instead
we edit the SAME image in place: detect the face (which stays untouched) and
recolour only the garment region to the exact colour the user requested. This
guarantees the face is pixel-identical and the colour is exactly what the user
said (red = red, blue = blue).

Colouring is done in LAB space: the original garment's L (lightness/luminance)
channel is preserved so shading and creases remain, while the A/B channels are
set to the target colour — the garment looks recoloured rather than flat.
"""

# User-facing colour names -> RGB target. Organised longest-first so "navy blue"
# is not caught by "blue".
COLOR_MAP = {
    'magenta': (200, 40, 220),
    'maroon': (128, 30, 40),
    'purple': (150, 40, 210),
    'orange': (240, 130, 30),
    'yellow': (235, 210, 30),
    'navy blue': (40, 50, 130),
    'sky blue': (60, 170, 230),
    'light blue': (120, 180, 240),
    'navy': (40, 50, 130),
    'green': (30, 160, 80),
    'brown': (130, 75, 45),
    'olive': (125, 125, 55),
    'teal': (25, 150, 150),
    'gold': (215, 180, 50),
    'pink': (235, 115, 165),
    'gray': (150, 150, 150),
    'grey': (150, 150, 150),
    'white': (238, 235, 230),
    'black': (40, 40, 40),
    'red': (220, 35, 45),
    'blue': (35, 75, 215),
}


class OutfitEditService:
    """Recolour the garment on an existing baby image, keeping its face intact."""

    def __init__(self):
        self._face = None

    def _parse_color(self, outfit_text):
        """Return the RGB tuple for a colour name found in the outfit text, or None."""
        text = (outfit_text or '').lower()
        for name, rgb in sorted(COLOR_MAP.items(), key=lambda kv: len(kv[0]), reverse=True):
            if name in text:
                return rgb
        return None

    def _detect_face(self, image_path):
        from PIL import Image
        from .image_processing_service import ImageProcessingService
        service = ImageProcessingService()
        faces = service._dlib_faces(image_path)
        if not faces:
            faces = service._opencv_faces(image_path)
        if not faces:
            return None
        width, height = Image.open(image_path).size
        return service._best_face(faces, width, height)  # (top, right, bottom, left)

    @staticmethod
    def _skin_mask(bgr):
        import cv2
        import numpy as np
        ycr = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb).astype(np.int32)
        y, cr, cb = ycr[..., 0], ycr[..., 1], ycr[..., 2]
        return (cr > 133) & (cr < 173) & (cb > 77) & (cb < 127) & (y > 80) & (y < 215)

    @staticmethod
    def _background_estimate(bgr):
        import numpy as np
        h, w = bgr.shape[:2]
        m = 8
        patches = [
            bgr[0:m, 0:m],
            bgr[0:m, w - m:w],
            bgr[h - m - 1:h - 1, 0:m],
            bgr[h - m - 1:h - 1, w - m:w],
        ]
        return np.mean(np.concatenate(patches), axis=(0, 1))

    def _garment_mask(self, bgr, bg):
        import numpy as np
        h, w = bgr.shape[:2]

        if self._face:
            top, right, bottom, left = self._face
            face_height = bottom - top
            row_start = int(bottom + face_height * 0.15)  # just below the chin
        else:
            row_start = int(h * 0.50)
        row_start = max(0, min(row_start, int(h * 0.90)))
        row_end = int(h * 0.97)

        col_start = int(w * 0.06)
        col_end = int(w * 0.94)

        mask = np.zeros((h, w), dtype=bool)
        mask[row_start:row_end, col_start:col_end] = True

        # Do not recolour skin (neck / hands) or the studio background.
        mask &= ~self._skin_mask(bgr)
        bg_distance = np.linalg.norm(bgr.astype(np.float32) - bg, axis=2)
        mask &= bg_distance > 35

        # Small morphological cleanup removes isolated background speckles.
        return self._clean(mask)

    @staticmethod
    def _clean(mask):
        import cv2
        import numpy as np
        m = mask.astype(np.uint8) * 255
        kernel = np.ones((5, 5), np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, kernel)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, kernel)
        return m > 0

    @staticmethod
    def _recolor(bgr, mask, rgb_target):
        import cv2
        import numpy as np
        target = np.zeros((1, 1, 3), dtype=np.uint8)
        target[0, 0] = (rgb_target[2], rgb_target[1], rgb_target[0])  # RGB -> BGR
        target_lab = cv2.cvtColor(target, cv2.COLOR_BGR2LAB)[0, 0]

        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        lab[..., 1][mask] = target_lab[1]
        lab[..., 2][mask] = target_lab[2]
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    def edit_outfit(self, image_path, outfit_text):
        """Recolour the garment on image_path in place. Returns True on success,
        False if no recognised colour or the edit could not be applied."""
        import cv2
        from PIL import Image

        rgb = self._parse_color(outfit_text)
        if rgb is None:
            return False

        bgr = cv2.imread(image_path)
        if bgr is None:
            return False

        self._face = self._detect_face(image_path)
        bg = self._background_estimate(bgr)
        mask = self._garment_mask(bgr, bg)
        if not mask.any():
            return False

        result = self._recolor(bgr, mask, rgb)
        try:
            pil = Image.fromarray(cv2.cvtColor(result, cv2.COLOR_BGR2RGB))
            pil.save(image_path, quality=95)
            return True
        except BaseException:
            return False