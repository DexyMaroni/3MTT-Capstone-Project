"""Download product photos for the demo listings from Wikimedia Commons.

Run with:  python manage.py fetch_images

Commons is used rather than a stock-photo site for two reasons: it needs no
API key, and every file carries an explicit free licence. Most of these are
CC BY or CC BY-SA, which *require* credit to be given, so the photographer
and licence are saved onto the listing and shown under the picture.

Re-running skips listings that already have an image. Use --force to
replace them.
"""

import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from PIL import Image, ImageOps

from listings.models import Listing

API = 'https://commons.wikimedia.org/w/api.php'

# Wikimedia rejects generic agents outright. Their policy asks that a tool
# identify itself and say where it comes from:
# https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
USER_AGENT = (
    'FarmLink-Capstone/1.0 '
    '(3MTT student project; https://github.com/topics/django) '
    'Python-urllib'
)

# Downloads are spaced out and retried on 429. Commons is donated
# infrastructure -- hammering it is both rude and self-defeating.
REQUEST_GAP = 1.5
MAX_RETRIES = 4

# Chosen by hand from Commons search results. Automated "take the top hit"
# picks up seedlings, botanical diagrams and 19th-century seed catalogues,
# none of which look like something you would buy.
PHOTOS = {
    'Fresh Tomatoes':                'Tomatoes in basket 2022 G1.jpg',
    'Scotch Bonnet Peppers':         'Scotch bonnet chili pepper.jpg',
    'Ugu (Fluted Pumpkin) Leaves':   'Flutted Pumpkin at Songhai Farm, Rivers State.jpg',
    'White Yam Tubers':              'Tubers of yam for sale.jpg',
    'Sweet Potatoes':                'Sweet potatoes exposed - DSCF7301.JPG',
    'Garri (Yellow)':                'Yellow Garri.jpg',
    'Local Rice (Ofada)':            'Ofada Rice.jpg',
    'Yellow Maize':                  'Drying maize corns (Himachal Pradesh),1.jpg',
    'Pearl Millet':                  'Food grain pearl millet 1.jpg',
    'Sweet Pineapple':               'Picture of Pineapple At Fruit Garden Market.jpg',
    'Agbalumo (African Star Apple)': 'AFRICAN STAR APPLE IN MARKET.jpg',
    'Plantain Bunch':                'Plantain bunch recently harvested.jpg',
    'Brown Beans (Oloyin)':          'Patterned cowpea (20240714).jpg',
    'Raw Groundnuts':                'Groundnut10.jpg',
    'Crate of Eggs':                 'A Tray Of Eggs.jpg',
    'Fresh Cow Milk':                'Raw Milk in container.jpg',
}

# What each photo actually shows, for screen readers. Written by hand because
# the command downloads a file it cannot look at -- and alt text that just
# repeats the title tells a blind user nothing the heading has not said.
DESCRIPTIONS = {
    'Fresh Tomatoes': 'a woven basket heaped with ripe red tomatoes',
    'Scotch Bonnet Peppers': 'a pile of small round scotch bonnet peppers, orange and red',
    'Ugu (Fluted Pumpkin) Leaves': 'broad green fluted pumpkin leaves growing on a farm',
    'White Yam Tubers': 'long brown yam tubers laid out for sale at a market stall',
    'Sweet Potatoes': 'orange-fleshed sweet potatoes with the soil still on them',
    'Garri (Yellow)': 'a bowl of coarse yellow garri granules',
    'Local Rice (Ofada)': 'a heap of unpolished brown ofada rice grains',
    'Yellow Maize': 'yellow maize kernels spread out to dry in the sun',
    'Pearl Millet': 'small round grey-brown pearl millet grains in a heap',
    'Sweet Pineapple': 'a ripe golden pineapple on display at a fruit market',
    'Agbalumo (African Star Apple)': 'orange agbalumo fruits piled in a bowl at a market',
    'Plantain Bunch': 'a large bunch of green plantains freshly cut from the tree',
    'Brown Beans (Oloyin)': 'speckled brown honey beans filling the frame',
    'Raw Groundnuts': 'raw groundnuts in their shells gathered in a basket',
    'Crate of Eggs': 'rows of brown chicken eggs in a cardboard tray',
    'Fresh Cow Milk': 'fresh white milk in a metal container',
}

# Ask Commons for something bigger than we need, so there are spare pixels
# to crop away before the final resize.
SOURCE_WIDTH = 2400

# Every photo is stored at exactly this size and ratio. Doing the crop here
# rather than in CSS means the grid is even no matter what the browser does
# with object-fit, and the detail page gets a sharp image on a 2x screen.
CARD_SIZE = (1200, 900)          # 4:3
JPEG_QUALITY = 87


def crop_to_ratio(image, ratio):
    """Trim the long side so the picture is exactly `ratio`, keeping the middle.

    Produce is almost always centred in these photos, so a centre crop is
    safe; the alternative -- squashing a portrait photo into a landscape box
    -- makes everything look wrong.
    """
    width, height = image.size
    if width / height > ratio:               # too wide: take the sides off
        new_width = round(height * ratio)
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height))
    new_height = round(width / ratio)        # too tall: take top and bottom off
    top = (height - new_height) // 2
    return image.crop((0, top, width, top + new_height))


def strip_html(value):
    """Commons returns the artist as an HTML fragment, often a link."""
    text = re.sub(r'<[^>]+>', '', value or '')
    return re.sub(r'\s+', ' ', text).strip()


class Command(BaseCommand):
    help = 'Fetch freely licensed product photos from Wikimedia Commons.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Replace photos on listings that already have one.',
        )

    def handle(self, *args, **options):
        listings = {listing.title: listing for listing in Listing.objects.all()}

        wanted = {}
        for title, filename in PHOTOS.items():
            listing = listings.get(title)
            if listing is None:
                self.stdout.write(self.style.WARNING(f'  no listing named "{title}"'))
            elif listing.image and not options['force']:
                self.stdout.write(f'  skipping {title} (already has one)')
            else:
                wanted[filename] = listing

        if not wanted:
            self.stdout.write('Nothing to fetch.')
            return

        metadata = self.fetch_metadata(list(wanted))

        saved = failed = 0
        for filename, listing in wanted.items():
            info = metadata.get(f'File:{filename}')
            if info is None:
                self.stdout.write(self.style.ERROR(f'  no metadata for {filename}'))
                failed += 1
                continue
            try:
                self.attach(listing, filename, info)
                saved += 1
            except Exception as exc:                       # noqa: BLE001
                self.stdout.write(self.style.ERROR(f'  {listing.title}: {exc}'))
                failed += 1
            time.sleep(REQUEST_GAP)                        # be polite to Commons

        self.stdout.write(self.style.SUCCESS(f'\nSaved {saved} photo(s), {failed} failed.'))

    def fetch_metadata(self, filenames):
        """One batched API call for every file we want."""
        titles = '|'.join(f'File:{name}' for name in filenames)
        query = urllib.parse.urlencode({
            'action': 'query', 'format': 'json', 'titles': titles,
            'prop': 'imageinfo', 'iiprop': 'url|extmetadata',
            'iiurlwidth': str(SOURCE_WIDTH),
        })
        data = json.loads(self.get(f'{API}?{query}', timeout=30))

        result = {}
        for page in data.get('query', {}).get('pages', {}).values():
            if 'imageinfo' in page:
                result[page['title']] = page['imageinfo'][0]
        return result

    def get(self, url, timeout=60):
        """Fetch a URL, backing off when Commons asks us to slow down."""
        request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                if exc.code != 429 or attempt == MAX_RETRIES:
                    raise
                wait = REQUEST_GAP * (2 ** attempt)
                self.stdout.write(f'    (rate limited, waiting {wait:.0f}s)')
                time.sleep(wait)
        raise RuntimeError('unreachable')

    def attach(self, listing, filename, info):
        # thumburl is a server-side resize; it is absent only for formats
        # Commons cannot thumbnail, in which case fall back to the original.
        source = info.get('thumburl') or info['url']
        raw = self.get(source)

        image = Image.open(io.BytesIO(raw))
        # Phone photos carry their rotation in EXIF rather than in the pixels.
        image = ImageOps.exif_transpose(image)
        # Commons holds PNGs, TIFFs and palette images too; JPEG needs RGB.
        if image.mode != 'RGB':
            image = image.convert('RGB')

        image = crop_to_ratio(image, CARD_SIZE[0] / CARD_SIZE[1])
        upscaled = image.width < CARD_SIZE[0]
        image = image.resize(CARD_SIZE, Image.LANCZOS)

        buffer = io.BytesIO()
        image.save(
            buffer, format='JPEG', quality=JPEG_QUALITY,
            optimize=True, progressive=True,
        )

        meta = info.get('extmetadata', {})
        artist = strip_html(meta.get('Artist', {}).get('value', '')) or 'Unknown'
        licence = meta.get('LicenseShortName', {}).get('value', 'see Wikimedia Commons')

        listing.image.save(
            f'{slugify(listing.title)}.jpg', ContentFile(buffer.getvalue()), save=False,
        )
        listing.image_credit = f'{artist} / {licence}, via Wikimedia Commons'
        listing.image_alt = DESCRIPTIONS.get(listing.title, '')
        listing.save(update_fields=['image', 'image_credit', 'image_alt'])

        size_kb = len(buffer.getvalue()) / 1024
        note = self.style.WARNING('  (source was small)') if upscaled else ''
        self.stdout.write(
            f'  {listing.title:32} {image.width}x{image.height}  {size_kb:5.0f} KB  '
            f'({licence}){note}'
        )
