import os
import re
import subprocess
import sys
import time

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from babies.models import BabyImage, GenerationPrompt, GenerationTemplate, ParentPhotoScan
from babies.tasks import process_baby_generation

User = get_user_model()


def download_face(filename, gender='male'):
    """Download a random face photo from randomuser.me."""
    api_url = f'https://randomuser.me/api/?gender={gender}'
    response = requests.get(api_url, timeout=30)
    response.raise_for_status()
    data = response.json()
    image_url = data['results'][0]['picture']['large']
    image_response = requests.get(image_url, timeout=30)
    image_response.raise_for_status()
    return ContentFile(image_response.content, name=filename)


def wait_for_server(url, timeout=30):
    for _ in range(timeout):
        try:
            health = requests.get(url, timeout=1)
            if health.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def start_cloudflared_tunnel(local_url):
    """Start a cloudflared tunnel and return the public HTTPS URL."""
    proc = subprocess.Popen(
        ['cloudflared', 'tunnel', '--url', local_url],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    url_pattern = re.compile(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com')
    deadline = time.time() + 60
    while time.time() < deadline:
        line = proc.stderr.readline()
        if not line:
            time.sleep(0.1)
            continue
        match = url_pattern.search(line)
        if match:
            return proc, match.group(0)
    proc.terminate()
    raise RuntimeError('Could not get cloudflared tunnel URL')


class Command(BaseCommand):
    help = 'Run an end-to-end generation test using two random faces, an admin prompt and template.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email', default='test_generation@example.com',
            help='User email to own the test records.'
        )
        parser.add_argument(
            '--use-cloudflared', action='store_true',
            help='Expose localhost via cloudflared so Replicate can download photos.'
        )
        parser.add_argument(
            '--base-url', default=None,
            help='Override BASE_URL for provider image URLs.'
        )
        parser.add_argument(
            '--skip-generation', action='store_true',
            help='Only create the scan/BabyImage rows without calling Replicate.'
        )

    def handle(self, *args, **options):
        email = options['email']
        use_cloudflared = options['use_cloudflared']
        base_url_override = options['base_url']
        skip_generation = options['skip_generation']

        self.stdout.write('Downloading test face images...')
        father_image = download_face('father.jpg', gender='male')
        mother_image = download_face('mother.jpg', gender='female')

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={'full_name': 'Test Generation User', 'is_active': True}
        )
        if not user.check_password('testpass123'):
            user.set_password('testpass123')
            user.save()

        self.stdout.write('Creating admin prompt and template...')
        prompt, _ = GenerationPrompt.objects.get_or_create(
            title='Test Baby Prompt',
            defaults={
                'content': 'A beautiful portrait of a {gender} baby with soft natural lighting, {age_stage}, {background}',
                'negative_prompt': 'blurry, distorted, ugly',
                'category': 'General Prompt',
                'status': 'active',
            }
        )
        template, _ = GenerationTemplate.objects.get_or_create(
            name='Test Studio Template',
            defaults={
                'category': 'Portrait',
                'theme': 'Studio',
                'background_type': 'Studio',
                'ai_prompt': 'professional studio portrait, clean background, soft lighting',
                'status': 'active',
            }
        )

        self.stdout.write('Creating approved parent photo scan...')
        scan = ParentPhotoScan.objects.create(
            user=user,
            father_photo=father_image,
            mother_photo=mother_image,
            overall_status='approved',
            father_scan_status='approved',
            mother_scan_status='approved',
            scan_result='Clean',
            confidence=1.0,
        )

        server = None
        tunnel_proc = None
        original_base_url = settings.BASE_URL

        try:
            if skip_generation:
                self.stdout.write(self.style.WARNING('Skipping generation as requested.'))
                return

            base_url = base_url_override or settings.BASE_URL

            if use_cloudflared:
                self.stdout.write('Starting Django server to serve media files...')
                server = subprocess.Popen(
                    [sys.executable, 'manage.py', 'runserver', '127.0.0.1:8000', '--noreload'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=settings.BASE_DIR,
                )
                if not wait_for_server('http://127.0.0.1:8000/api/health/', 30):
                    self.stdout.write(self.style.ERROR('Server did not start in time.'))
                    return
                self.stdout.write('Starting cloudflared tunnel...')
                tunnel_proc, base_url = start_cloudflared_tunnel('http://127.0.0.1:8000')
                self.stdout.write(f'Tunnel public URL: {base_url}')
                if not wait_for_server(f'{base_url}/api/health/', 60):
                    self.stdout.write(self.style.ERROR('Tunnel did not become reachable in time.'))
                    return

            settings.BASE_URL = base_url.rstrip('/')

            self.stdout.write('Creating BabyImage and running generation synchronously...')
            baby_image = BabyImage.objects.create(
                user=user,
                generation_type='initial',
                father_photo=scan.father_photo,
                mother_photo=scan.mother_photo,
                parent_photo_scan=scan,
                generation_template=template,
                gender='boy',
                age_stage='newborn',
                background='studio',
            )
            self.stdout.write(f'BabyImage created: {baby_image.id}')
            # Run the task in-process so the dynamic BASE_URL is respected.
            process_baby_generation(str(baby_image.id))

            baby_image.refresh_from_db()
            self.stdout.write(f'Generation status: {baby_image.generation_status}')
            self.stdout.write(f'Prompt used: {baby_image.generation_prompt_text}')
            self.stdout.write(f'AI provider: {baby_image.ai_provider}')
            self.stdout.write(f'External job ID: {baby_image.external_job_id}')
            if baby_image.generation_status == 'done':
                self.stdout.write(self.style.SUCCESS(f'Generated image: {baby_image.generated_image.url}'))
                self.stdout.write(f'Eyes similarity: {baby_image.eyes_similarity}')
                self.stdout.write(f'Face shape similarity: {baby_image.face_shape_similarity}')
                self.stdout.write(f'Skin tone similarity: {baby_image.skin_tone_similarity}')
            else:
                self.stdout.write(self.style.ERROR(f'Error: {baby_image.error_message}'))

        finally:
            settings.BASE_URL = original_base_url
            self.stdout.write('Stopping server and tunnel...')
            if tunnel_proc:
                tunnel_proc.terminate()
            if server:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except Exception:
                    server.kill()
            if tunnel_proc:
                try:
                    tunnel_proc.wait(timeout=5)
                except Exception:
                    tunnel_proc.kill()
