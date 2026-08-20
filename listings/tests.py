from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Listing

User = get_user_model()


class ListingModelTests(TestCase):
    def setUp(self):
        self.farmer = User.objects.create_user(
            username='farmer', password='pw', role=User.Role.FARMER
        )
        self.category = Category.objects.create(name='Grains')

    def test_slug_is_generated_from_category_name(self):
        self.assertEqual(self.category.slug, 'grains')

    def test_unit_label_pluralises_with_the_quantity(self):
        listing = Listing.objects.create(
            farmer=self.farmer, category=self.category, title='Milk',
            price=Decimal('1400.00'), quantity_available=50,
            unit=Listing.Unit.LITRE,
        )
        self.assertEqual(listing.unit_label(1), 'litre')
        self.assertEqual(listing.unit_label(50), 'litres')
        # No argument means "however many are in stock".
        self.assertEqual(listing.unit_label(), 'litres')

    def test_unit_label_adds_es_after_a_sibilant(self):
        # The case a naive +"s" gets wrong: "bunchs".
        listing = Listing.objects.create(
            farmer=self.farmer, category=self.category, title='Plantain',
            price=Decimal('3200.00'), quantity_available=18,
            unit=Listing.Unit.BUNCH,
        )
        self.assertEqual(listing.unit_label(1), 'bunch')
        self.assertEqual(listing.unit_label(18), 'bunches')

    def test_in_stock_requires_active_and_quantity(self):
        listing = Listing.objects.create(
            farmer=self.farmer, category=self.category, title='Maize',
            price=Decimal('1500.00'), quantity_available=10,
        )
        self.assertTrue(listing.in_stock)

        listing.quantity_available = 0
        self.assertFalse(listing.in_stock)

        listing.quantity_available = 10
        listing.is_active = False
        self.assertFalse(listing.in_stock)

    def test_available_queryset_excludes_hidden_and_empty(self):
        Listing.objects.create(
            farmer=self.farmer, category=self.category, title='Live',
            price=Decimal('100.00'), quantity_available=5,
        )
        Listing.objects.create(
            farmer=self.farmer, category=self.category, title='Sold out',
            price=Decimal('100.00'), quantity_available=0,
        )
        Listing.objects.create(
            farmer=self.farmer, category=self.category, title='Hidden',
            price=Decimal('100.00'), quantity_available=5, is_active=False,
        )

        titles = list(Listing.objects.available().values_list('title', flat=True))
        self.assertEqual(titles, ['Live'])


class ListingViewTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Tubers')
        self.farmer = User.objects.create_user(
            username='amina', password='pw', role=User.Role.FARMER, location='Jos'
        )
        self.other_farmer = User.objects.create_user(
            username='tunde', password='pw', role=User.Role.FARMER
        )
        self.buyer = User.objects.create_user(
            username='chidi', password='pw', role=User.Role.BUYER
        )
        self.listing = Listing.objects.create(
            farmer=self.farmer, category=self.category, title='White Yam',
            price=Decimal('4500.00'), quantity_available=20,
        )

    def test_marketplace_lists_available_produce(self):
        response = self.client.get(reverse('listings:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'White Yam')

    def test_search_matches_title(self):
        response = self.client.get(reverse('listings:list'), {'q': 'yam'})
        self.assertContains(response, 'White Yam')

        response = self.client.get(reverse('listings:list'), {'q': 'zucchini'})
        self.assertNotContains(response, 'White Yam')

    def test_search_matches_farmer_location(self):
        response = self.client.get(reverse('listings:list'), {'q': 'Jos'})
        self.assertContains(response, 'White Yam')

    def test_buyer_cannot_open_farmer_dashboard(self):
        self.client.force_login(self.buyer)
        response = self.client.get(reverse('listings:dashboard'))
        self.assertRedirects(response, reverse('listings:list'))

    def test_farmer_creates_listing_owned_by_themselves(self):
        self.client.force_login(self.other_farmer)
        response = self.client.post(
            reverse('listings:create'),
            {
                'title': 'Cassava', 'category': self.category.pk,
                'description': 'Fresh', 'price': '900.00', 'unit': 'kg',
                'quantity_available': 50, 'is_active': 'on',
            },
        )
        self.assertRedirects(response, reverse('listings:dashboard'))
        listing = Listing.objects.get(title='Cassava')
        self.assertEqual(listing.farmer, self.other_farmer)

    def test_farmer_cannot_edit_another_farmers_listing(self):
        self.client.force_login(self.other_farmer)
        response = self.client.get(reverse('listings:update', args=[self.listing.pk]))
        self.assertEqual(response.status_code, 404)

    def test_hidden_listing_is_not_public(self):
        self.listing.is_active = False
        self.listing.save()
        response = self.client.get(reverse('listings:detail', args=[self.listing.pk]))
        self.assertRedirects(response, reverse('listings:list'))
