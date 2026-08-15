import os
from django.db import transaction
from ..models import ParentPhotoScan


def _dispatch_scan_task(scan_id):
    from ..tasks import process_parent_photo_scan
    process_parent_photo_scan.delay(scan_id)


class ParentPhotoScanService:
    def __init__(self, user):
        self.user = user

    def create_scan(self, father_photo, mother_photo):
        scan = ParentPhotoScan.objects.create(
            user=self.user,
            father_photo=father_photo,
            mother_photo=mother_photo,
            overall_status='pending',
            father_scan_status='pending',
            mother_scan_status='pending',
        )
        _dispatch_scan_task(str(scan.id))
        return scan

    def get_scan(self, scan_id):
        return ParentPhotoScan.objects.get(id=scan_id, user=self.user)

    def get_clean_scan(self, scan_id):
        scan = self.get_scan(scan_id)
        if scan.overall_status != 'approved':
            raise ValueError('Parent photos are not approved for generation.')
        return scan

    def reset_scan(self, scan_id):
        """Admin reset: delete photos and clear scan results."""
        scan = ParentPhotoScan.objects.get(id=scan_id)
        self._delete_photo_file(scan.father_photo)
        self._delete_photo_file(scan.mother_photo)
        scan.father_photo.delete(save=False)
        scan.mother_photo.delete(save=False)
        scan.father_scan_status = 'pending'
        scan.mother_scan_status = 'pending'
        scan.father_scan_details = {}
        scan.mother_scan_details = {}
        scan.overall_status = 'pending'
        scan.scan_result = 'Pending Analysis'
        scan.confidence = 0
        scan.reason = ''
        scan.moderator_notes = ''
        scan.save()
        return scan

    def rescan(self, scan_id):
        scan = ParentPhotoScan.objects.get(id=scan_id)
        scan.father_scan_status = 'pending'
        scan.mother_scan_status = 'pending'
        scan.father_scan_details = {}
        scan.mother_scan_details = {}
        scan.overall_status = 'scanning'
        scan.scan_result = 'Scanning...'
        scan.confidence = 0
        scan.reason = ''
        scan.save()
        _dispatch_scan_task(str(scan.id))
        return scan

    def _delete_photo_file(self, field):
        try:
            if field and field.name:
                path = field.path
                if os.path.isfile(path):
                    os.remove(path)
        except Exception:
            pass

    def admin_list(self, search=None, status=None):
        qs = ParentPhotoScan.objects.all().select_related('user')
        if status:
            qs = qs.filter(overall_status=status)
        if search:
            qs = qs.filter(user__email__icontains=search)
        return qs

    def admin_get(self, scan_id):
        return ParentPhotoScan.objects.select_related('user').get(id=scan_id)

    def admin_update(self, scan_id, **fields):
        allowed = {'status', 'moderator_notes'}
        update_data = {k: v for k, v in fields.items() if k in allowed}
        with transaction.atomic():
            scan = self.admin_get(scan_id)
            for key, value in update_data.items():
                setattr(scan, key, value)
            scan.save(update_fields=list(update_data.keys()) + ['updated_at'])
        return scan

    def admin_delete(self, scan_id):
        scan = self.admin_get(scan_id)
        self.reset_scan(scan.id)
        scan.delete()
