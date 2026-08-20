"""Attach the bundled produce photos to the demo listings.

Run with:  python manage.py load_images

The photos in listings/seed_images/ ship with the repository, so this works
with no internet connection -- unlike fetch_images, which downloads them from
Wikimedia Commons. That matters when somebody is setting the project up on a
machine you do not control.

The two commands are complementary:

    load_images   offline, instant, uses the committed copies
    fetch_images  online, re-downloads originals, used to build that set

Re-running skips listings that already have a photo. Use --force to replace.
"""

import json
import shutil

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from listings.models import Listing

SEED_DIR = settings.BASE_DIR / 'listings' / 'seed_images'
MANIFEST = SEED_DIR / 'manifest.json'


class Command(BaseCommand):
    help = 'Attach the bundled seed photos to listings (works offline).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Replace photos on listings that already have one.',
        )

    def handle(self, *args, **options):
        if not MANIFEST.exists():
            raise CommandError(
                f'No manifest at {MANIFEST}.\n'
                'The bundled photos are missing. Run "manage.py fetch_images" '
                'to download them from Wikimedia Commons instead.'
            )

        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
        listings = {listing.title: listing for listing in Listing.objects.all()}

        attached = skipped = missing = 0

        for title, entry in manifest.items():
            listing = listings.get(title)
            if listing is None:
                self.stdout.write(
                    self.style.WARNING(f'  no listing called "{title}" -- run seed_demo first')
                )
                missing += 1
                continue

            if listing.image and not options['force']:
                skipped += 1
                continue

            source = SEED_DIR / entry['file']
            if not source.exists():
                self.stdout.write(self.style.ERROR(f'  missing file: {source.name}'))
                missing += 1
                continue

            with source.open('rb') as handle:
                # save=False so the row is written once, below, rather than twice.
                listing.image.save(entry['file'], File(handle), save=False)
            listing.image_credit = entry.get('credit', '')
            listing.image_alt = entry.get('alt', '')
            listing.save(update_fields=['image', 'image_credit', 'image_alt'])

            attached += 1
            self.stdout.write(f'  {title}')

        summary = f'Attached {attached} photo(s)'
        if skipped:
            summary += f', skipped {skipped} that already had one'
        if missing:
            summary += f', {missing} missing'
        style = self.style.WARNING if missing else self.style.SUCCESS
        self.stdout.write(style(summary + '.'))

        if skipped and not options['force']:
            self.stdout.write('Use --force to replace existing photos.')
