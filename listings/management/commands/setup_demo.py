"""One command to get a working, populated site from a fresh clone.

Run with:  python manage.py setup_demo

Equivalent to running these in order:

    python manage.py migrate
    python manage.py seed_demo
    python manage.py load_images

Each of those is safe to re-run on its own; so is this. It exists so that
setting the project up is one instruction rather than three remembered in the
right order -- the photos have to come last, because they attach to listings
that seed_demo creates.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from listings.models import Listing


class Command(BaseCommand):
    help = 'Create the database, load demo data, and attach the produce photos.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            default='farmlink123',
            help='Password for every demo account (default: farmlink123).',
        )
        parser.add_argument(
            '--skip-images', action='store_true',
            help='Leave listings without photos (they show a letter placeholder).',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\n[1/3] Creating database tables'))
        call_command('migrate', verbosity=0)
        self.stdout.write('  done')

        self.stdout.write(self.style.MIGRATE_HEADING('\n[2/3] Loading demo data'))
        call_command('seed_demo', password=options['password'], verbosity=0)
        self.stdout.write(
            f'  {Listing.objects.count()} listings, '
            f'{Listing.objects.values("farmer").distinct().count()} farmers'
        )

        if options['skip_images']:
            self.stdout.write(self.style.MIGRATE_HEADING('\n[3/3] Photos skipped'))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING('\n[3/3] Attaching produce photos'))
            call_command('load_images', verbosity=0)
            with_photo = Listing.objects.exclude(image='').count()
            self.stdout.write(f'  {with_photo} of {Listing.objects.count()} listings have a photo')

        password = options['password']
        self.stdout.write(self.style.SUCCESS(
            '\nReady. Start the server with:\n'
            '    python manage.py runserver\n'
            '\nThen open http://127.0.0.1:8000/ and sign in as any of these\n'
            f'(password "{password}"):\n'
            '    Buyer   chidi_buys      browse, add to cart, check out\n'
            '    Farmer  amina_farms     dashboard, listings, incoming orders\n'
            '    Admin   admin           http://127.0.0.1:8000/admin/\n'
        ))
