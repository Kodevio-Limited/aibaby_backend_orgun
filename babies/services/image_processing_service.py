"""Local post-processing for generated baby images.

The provider (PhotoMaker) tends to render full bodies with hands, fingers and
feet. We crop every generated image to a tight head-and-shoulders portrait
around the detected face so the final output is a clean face-first baby photo.
"""


class ImageProcessingService:
    """Detect a face and crop the image to a head-and-shoulders portrait.

    Uses face_recognition (dlib) first, falls back to OpenCV's Haar cascade.
    If no face is found the original image is returned untouched so a failed
    detection never destroys a successful generation.
    """

    def _crop_box(self, img_shape, top, right, bottom, left):
        height, width = img_shape[:2]
        face_width = right - left
        face_height = bottom - top

        center_x = (left + right) / 2
        # Bias the crop upward (head fills the frame) — the face box from dlib
        # already starts around the eyebrows, so we keep most of the head above.
        center_y = top + face_height * 0.45

        crop_width = face_width * 3.0
        crop_height = face_height * 3.6

        left_c = int(center_x - crop_width / 2)
        top_c = int(center_y - crop_height / 2)
        right_c = int(center_x + crop_width / 2)
        bottom_c = int(center_y + crop_height / 2)

        left_c = max(0, left_c)
        top_c = max(0, top_c)
        right_c = min(width, right_c)
        bottom_c = min(height, bottom_c)

        if right_c - left_c < 60 or bottom_c - top_c < 60:
            return None
        return (left_c, top_c, right_c, bottom_c)

    def _dlib_face_box(self, image_path):
        try:
            import face_recognition
            img = face_recognition.load_image_file(image_path)
            locations = face_recognition.face_locations(img, model='hog')
            if not locations:
                return None
            return locations[0]
        except BaseException:
            return None

    def _opencv_face_box(self, image_path):
        try:
            import cv2
            img = cv2.imread(image_path)
            if img is None:
                return None
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            cascade = cv2.CascadeClassifier(cascade_path)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
            if len(faces) == 0:
                return None
            x, y, w, h = faces[0]
            return (y, x + w, y + h, x)  # top, right, bottom, left
        except BaseException:
            return None

    def crop_to_face(self, image_path):
        """Return a PIL Image cropped to the head-and-shoulders portrait, or None."""
        from PIL import Image

        box = self._dlib_face_box(image_path)
        if box is None:
            box = self._opencv_face_box(image_path)
        if box is None:
            return None

        top, right, bottom, left = box
        try:
            import face_recognition
            import numpy as np
            img_shape = face_recognition.load_image_file(image_path).shape
        except BaseException:
            try:
                import cv2
                img_shape = cv2.imread(image_path).shape
            except BaseException:
                return None

        crop = self._crop_box(img_shape, top, right, bottom, left)
        if crop is None:
            return None

        try:
            image = Image.open(image_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            return image.crop(crop)
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