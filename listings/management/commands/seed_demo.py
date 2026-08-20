"""Populate the database with realistic demo data.

Run with:  python manage.py seed_demo
Safe to re-run -- it uses get_or_create, so it won't pile up duplicates.
"""

import random
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from listings.models import Category, Listing

User = get_user_model()

CATEGORIES = [
    ('Vegetables', 'Leafy greens, peppers, tomatoes and more'),
    ('Tubers', 'Yam, cassava, potatoes and cocoyam'),
    ('Grains', 'Rice, maize, millet and sorghum'),
    ('Fruits', 'Seasonal fresh fruit'),
    ('Legumes', 'Beans, groundnuts and soya'),
    ('Livestock & Dairy', 'Eggs, milk and poultry'),
]

FARMERS = [
    ('amina_farms', 'Amina', 'Bello', 'Jos, Plateau'),
    ('okon_greens', 'Okon', 'Effiong', 'Uyo, Akwa Ibom'),
    ('tunde_agro', 'Tunde', 'Adeyemi', 'Ibadan, Oyo'),
]

BUYERS = [
    ('chidi_buys', 'Chidi', 'Nwosu', 'Enugu, Enugu'),
    ('grace_market', 'Grace', 'Ekpo', 'Abuja, FCT'),
]

# (title, category, price, unit, quantity, description)
PRODUCE = [
    ('Fresh Tomatoes', 'Vegetables', '1800.00', 'basket', 24,
     'Firm, ripe tomatoes picked this morning. Great for stew and sauces.'),
    ('Scotch Bonnet Peppers', 'Vegetables', '2500.00', 'basket', 15,
     'Very hot and aromatic. Sold by the small basket.'),
    ('Ugu (Fluted Pumpkin) Leaves', 'Vegetables', '500.00', 'bunch', 60,
     'Cut fresh daily. Tender leaves, no stalks.'),
    ('White Yam Tubers', 'Tubers', '4500.00', 'piece', 40,
     'Large, well-cured tubers from this season. Stores for months.'),
    ('Sweet Potatoes', 'Tubers', '1200.00', 'kg', 180,
     'Orange-fleshed and sweet. Good for roasting and porridge.'),
    ('Garri (Yellow)', 'Tubers', '2200.00', 'bag', 30,
     'Processed and sun-dried in small batches. Fine grain.'),
    ('Local Rice (Ofada)', 'Grains', '3800.00', 'bag', 22,
     'Stone-free, destoned twice. Rich aroma when cooked.'),
    ('Yellow Maize', 'Grains', '1500.00', 'kg', 300,
     'Dried to 13% moisture. Suitable for pap or animal feed.'),
    ('Pearl Millet', 'Grains', '1700.00', 'kg', 90,
     'Cleaned and bagged. Ideal for kunu and porridge.'),
    ('Sweet Pineapple', 'Fruits', '900.00', 'piece', 75,
     'Field-ripened, extra sweet. Sold whole.'),
    ('Agbalumo (African Star Apple)', 'Fruits', '600.00', 'basket', 8,
     'In season now. Sold in small baskets of about 20 fruits.'),
    ('Plantain Bunch', 'Fruits', '3200.00', 'bunch', 18,
     'Mature green bunches, will ripen in about five days.'),
    ('Brown Beans (Oloyin)', 'Legumes', '2900.00', 'kg', 140,
     'Sweet honey beans, hand-sorted and weevil-free.'),
    ('Raw Groundnuts', 'Legumes', '2100.00', 'kg', 110,
     'Freshly harvested and dried. Shells intact.'),
    ('Crate of Eggs', 'Livestock & Dairy', '5200.00', 'crate', 35,
     'Thirty large eggs per crate, collected daily.'),
    ('Fresh Cow Milk', 'Livestock & Dairy', '1400.00', 'litre', 50,
     'Unpasteurised, from grass-fed cattle. Boil before use.'),
]


class Command(BaseCommand):
    help = 'Create demo categories, farmers, buyers and produce listings.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            default='farmlink123',
            help='Password given to every demo account (default: farmlink123).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options['password']

        categories = {}
        for name, description in CATEGORIES:
            category, _ = Category.objects.get_or_create(
                name=name, defaults={'description': description}
            )
            categories[name] = category
        self.stdout.write(f'Categories ready: {len(categories)}')

        farmers = []
        for username, first, last, location in FARMERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': f'{username}@example.com',
                    'role': User.Role.FARMER,
                    'location': location,
                    'phone': f'080{random.randint(10000000, 99999999)}',
                },
            )
            if created:
                user.set_password(password)
                user.save()
            farmers.append(user)

        for username, first, last, location in BUYERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first,
                    'last_name': last,
                    'email': f'{username}@example.com',
                    'role': User.Role.BUYER,
                    'location': location,
                    'phone': f'081{random.randint(10000000, 99999999)}',
                },
            )
            if created:
                user.set_password(password)
                user.save()

        # An admin account so /admin/ is reachable without a separate step.
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@example.com',
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            admin.set_password(password)
            admin.save()

        self.stdout.write(f'Users ready: {len(FARMERS)} farmers, {len(BUYERS)} buyers, 1 admin')

        created_count = 0
        for index, (title, category_name, price, unit, quantity, description) in enumerate(PRODUCE):
            # Spread listings across the farmers so each dashboard has content.
            farmer = farmers[index % len(farmers)]
            _, created = Listing.objects.get_or_create(
                title=title,
                farmer=farmer,
                defaults={
                    'category': categories[category_name],
                    'description': description,
                    'price': Decimal(price),
                    'unit': unit,
                    'quantity_available': quantity,
                },
            )
            created_count += int(created)

        self.stdout.write(f'Listings created: {created_count}')
        self.stdout.write(
            self.style.SUCCESS(
                f'\nDemo data ready. Log in as any of these with password "{password}":\n'
                f'  Farmers: {", ".join(f[0] for f in FARMERS)}\n'
                f'  Buyers:  {", ".join(b[0] for b in BUYERS)}\n'
                f'  Admin:   admin  (http://127.0.0.1:8000/admin/)\n\n'
                f'Listings start without photos. Run "python manage.py '
                f'fetch_images" to pull them from Wikimedia Commons.'
            )
        )
