class SimilarityService:
    def compare_faces(self, image_a_path, image_b_path):
        try:
            import face_recognition
            img_a = face_recognition.load_image_file(image_a_path)
            img_b = face_recognition.load_image_file(image_b_path)
            enc_a = face_recognition.face_encodings(img_a)
            enc_b = face_recognition.face_encodings(img_b)
            if not enc_a or not enc_b:
                return None
            distance = face_recognition.face_distance([enc_b[0]], enc_a[0])[0]
            return round((1 - distance) * 100, 1)
        except Exception:
            return None

    def compare_skin_tone(self, image_a_path, image_b_path):
        try:
            import cv2
            import numpy as np
            img_a = cv2.cvtColor(cv2.imread(image_a_path), cv2.COLOR_BGR2LAB)
            img_b = cv2.cvtColor(cv2.imread(image_b_path), cv2.COLOR_BGR2LAB)
            avg_a = img_a.reshape(-1, 3).mean(axis=0)
            avg_b = img_b.reshape(-1, 3).mean(axis=0)
            delta_e = np.linalg.norm(avg_a - avg_b)
            return round(max(0, 100 - delta_e), 1)
        except Exception:
            return None
