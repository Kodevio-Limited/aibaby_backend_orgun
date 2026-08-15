import hashlib
from django.core.files.storage import default_storage


class ScanService:
    """Lightweight local verification of parent photos.

    NSFW detection is intentionally skipped for now (per product decision).
    Checks performed:
      - at least one face is detected
      - exact duplicate file hash versus user's other clean scans
    """

    def __init__(self):
        pass

    def _file_hash(self, file_path):
        hasher = hashlib.md5()
        with default_storage.open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _detect_face(self, image_path):
        try:
            import face_recognition
            img = face_recognition.load_image_file(image_path)
            locations = face_recognition.face_locations(img)
            return len(locations)
        except Exception:
            return 0

    def _find_duplicate_scan(self, scan_model, user_id, file_hash, exclude_scan_id):
        return scan_model.objects.filter(
            user_id=user_id,
            overall_status='approved',
        ).exclude(
            id=exclude_scan_id,
        ).filter(
            father_scan_details__file_hash=file_hash,
        ).first() or scan_model.objects.filter(
            user_id=user_id,
            overall_status='approved',
        ).exclude(
            id=exclude_scan_id,
        ).filter(
            mother_scan_details__file_hash=file_hash,
        ).first()

    def scan_photo(self, scan, field_name, user_id):
        """Scan a single photo field on a ParentPhotoScan instance.

        Returns a tuple (status, result_label, details_dict).
        """
        photo_field = getattr(scan, field_name)
        if not photo_field:
            return 'rejected', 'No Face Detected', {'error': 'No photo uploaded'}

        image_path = photo_field.path if hasattr(photo_field, 'path') else photo_field.name
        file_hash = self._file_hash(image_path)
        face_count = self._detect_face(image_path)

        details = {
            'file_hash': file_hash,
            'face_count': face_count,
        }

        if face_count == 0:
            return 'rejected', 'No Face Detected', details

        duplicate = self._find_duplicate_scan(
            scan._meta.model,
            user_id,
            file_hash,
            scan.id,
        )
        if duplicate:
            details['duplicate_scan_id'] = str(duplicate.id)
            return 'rejected', 'Duplicate', details

        details['confidence'] = 1.0
        return 'approved', 'Clean', details

    def run_scan(self, scan):
        """Run the full scan for father + mother photos and update the scan record."""
        scan.overall_status = 'scanning'
        scan.scan_result = 'Scanning...'
        scan.confidence = 0
        scan.reason = ''
        scan.save(update_fields=['overall_status', 'scan_result', 'confidence', 'reason', 'updated_at'])

        father_status, father_result, father_details = self.scan_photo(scan, 'father_photo', scan.user_id)
        mother_status, mother_result, mother_details = self.scan_photo(scan, 'mother_photo', scan.user_id)

        scan.father_scan_status = father_status
        scan.mother_scan_status = mother_status
        scan.father_scan_details = father_details
        scan.mother_scan_details = mother_details

        if father_status == 'rejected' or mother_status == 'rejected':
            scan.overall_status = 'rejected'
            scan.scan_result = father_result if father_status == 'rejected' else mother_result
            scan.confidence = 0
            scan.reason = f"Father: {father_result}, Mother: {mother_result}"
        elif father_status == 'flagged' or mother_status == 'flagged':
            scan.overall_status = 'flagged'
            scan.scan_result = 'Pending Analysis'
            scan.confidence = 0
            scan.reason = 'One or more photos require manual review.'
        else:
            scan.overall_status = 'approved'
            scan.scan_result = 'Clean'
            scan.confidence = 1.0
            scan.reason = ''

        scan.save()
        return scan
