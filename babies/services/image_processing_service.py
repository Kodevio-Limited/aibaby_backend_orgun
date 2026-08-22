"""Local post-processing for generated baby images.

The provider (PhotoMaker) tends to render full bodies, stray hands/fingers,
and sometimes multiple/duplicated subjects in one frame. We post-process every
generated image into a consistent passport-style portrait:

  * the single best (largest, most central) face is chosen,
  * the crop has a fixed 3:4 portrait aspect ratio,
  * the face is placed at a deterministic upper-half position (face box top at
    ~30% of the frame height, horizontally centred) regardless of where the
    face happened to be rendered, and
  * the result is resized to a fixed output resolution so every image is framed
    identically.
"""

PASSPORT_ASPECT = 3.0 / 4.0  # width / height (portrait)
OUTPUT_SIZE = (768, 1024)    # fixed output resolution (passport-like)


class ImageProcessingService:
    """Detect a face and normalise the image into a fixed passport-style portrait.

    Uses face_recognition (dlib) first, falls back to OpenCV's Haar cascade.
    If no face is found the original image is left untouched so a failed
    detection never destroys a successful generation.
    """

    def _dlib_faces(self, image_path):
        try:
            import face_recognition
            img = face_recognition.load_image_file(image_path)
            locations = face_recognition.face_locations(img, model='hog')
            return list(locations)
        except BaseException:
            return []

    def _opencv_faces(self, image_path):
        try:
            import cv2
            img = cv2.imread(image_path)
            if img is None:
                return []
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
            return [(y, x + w, y + h, x) for x, y, w, h in faces]  # top, right, bottom, left
        except BaseException:
            return []

    def _detect_faces(self, image_path):
        faces = self._dlib_faces(image_path)
        if faces:
            return faces
        return self._opencv_faces(image_path)

    @staticmethod
    def _best_face(faces, width, height):
        """Pick the primary subject: largest face, tie-broken by centre proximity."""
        def score(face):
            top, right, bottom, left = face
            area = (right - left) * (bottom - top)
            cx, cy = (left + right) / 2.0, (top + bottom) / 2.0
            distance = (cx - width / 2.0) ** 2 + (cy - height / 2.0) ** 2
            return area, -distance
        return max(faces, key=score)

    @staticmethod
    def _portrait_crop(box, width, height):
        """Compute a passport-style crop box with a DETERMINISTIC face position.

        Output aspect ratio is fixed (3:4). The face is horizontally centred
        and the top of the face box is anchored at 30% of the frame height, so
        the face ends up in the upper half regardless of where the model placed
        it. Returns (left, top, right, bottom) or None if it cannot fit.
        """
        top, right, bottom, left = box
        face_width = right - left
        face_height = bottom - top
        if face_width <= 0 or face_height <= 0:
            return None
        face_cx = (left + right) / 2.0

        # Head (including hair above the dlib eye/brow line) ≈ 1.45x face box.
        head_height = face_height * 1.45
        # Portrait rule: head occupies ~55% of frame height so the shoulders and
        # the top of the garment (whose colour the user controls) stay in frame.
        crop_height = head_height / 0.55
        crop_width = crop_height * PASSPORT_ASPECT

        face_top_ratio = 0.26  # face box top sits 26% down the frame
        crop_left = face_cx - crop_width / 2.0
        crop_top = top - face_top_ratio * crop_height

        # Shrink to fit the image bounds first (keeps face anchor fixed), then
        # translate minimally so the whole crop lies inside the canvas.
        if crop_width > width or crop_height > height:
            scale = min(width / crop_width, height / crop_height)
            if scale <= 0:
                return None
            crop_width *= scale
            crop_height *= scale
            crop_left = face_cx - crop_width / 2.0
            crop_top = top - face_top_ratio * crop_height

        crop_right = crop_left + crop_width
        crop_bottom = crop_top + crop_height

        if crop_width > width or crop_height > height:
            return None

        if crop_left < 0:
            shift = -crop_left
            crop_left += shift
            crop_right += shift
        if crop_right > width:
            shift = crop_right - width
            crop_left -= shift
            crop_right = width
        if crop_top < 0:
            shift = -crop_top
            crop_top += shift
            crop_bottom += shift
        if crop_bottom > height:
            shift = crop_bottom - height
            crop_top -= shift
            crop_bottom = height

        left_c = int(round(crop_left))
        top_c = int(round(crop_top))
        right_c = int(round(crop_right))
        bottom_c = int(round(crop_bottom))

        if right_c - left_c < 60 or bottom_c - top_c < 60:
            return None
        return (left_c, top_c, right_c, bottom_c)

    def crop_to_face(self, image_path):
        """Return a PIL Image normalised to the fixed passport-style portrait or None."""
        from PIL import Image

        faces = self._detect_faces(image_path)
        if not faces:
            return None

        try:
            with Image.open(image_path) as probe:
                width, height = probe.size
        except BaseException:
            return None

        box = self._best_face(faces, width, height)
        crop = self._portrait_crop(box, width, height)
        if crop is None:
            return None

        left, top, right, bottom = crop
        try:
            image = Image.open(image_path).convert('RGB')
            cropped = image.crop((left, top, right, bottom))
            return cropped.resize(OUTPUT_SIZE, Image.LANCZOS)
        except BaseException:
            return None

    def crop_and_save(self, image_path):
        """Crop the file at image_path in place. Returns True if cropped, else False."""
        cropped = self.crop_to_face(image_path)
        if cropped is None:
            return False
        try:
            cropped.save(image_path, quality=95)
            return True
        except BaseException:
            return False

    def create_face_crop(self, source_path):
        """Save a bare-face crop of a parent photo to storage.

        PhotoMaker blends reference images; asking it to consume only the FACE
        (not the whole body photo) makes the father/mother identity far more
        literal, so the generated baby resembles them more closely. Returns the
        storage-relative name (e.g. 'crops/...jpg') or None if no face / on error.
        """
        import io
        import uuid
        from PIL import Image

        faces = self._detect_faces(source_path)
        if not faces:
            return None

        try:
            with Image.open(source_path) as probe:
                width, height = probe.size
        except BaseException:
            return None

        box = self._best_face(faces, width, height)
        top, right, bottom, left = box
        face_w, face_h = right - left, bottom - top
        if face_w <= 0 or face_h <= 0:
            return None

        margin = 0.12
        c_left = max(0, int(left - face_w * margin))
        c_top = max(0, int(top - face_h * margin * 1.4))
        c_right = min(width, int(right + face_w * margin))
        c_bottom = min(height, int(bottom + face_h * margin))
        if (c_right - c_left) < 50 or (c_bottom - c_top) < 50:
            return None

        try:
            from django.core.files.base import ContentFile
            from django.core.files.storage import default_storage
            cropped = Image.open(source_path).convert('RGB').crop(
                (c_left, c_top, c_right, c_bottom)
            )
            buf = io.BytesIO()
            cropped.save(buf, format='JPEG', quality=95)
            return default_storage.save(
                f'crops/{uuid.uuid4()}.jpg', ContentFile(buf.getvalue())
            )
        except BaseException:
            return None