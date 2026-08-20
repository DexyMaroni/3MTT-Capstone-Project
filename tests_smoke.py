"""Renders every page in the app for the role that's meant to see it.

The per-app tests check behaviour; this file only asks "does the template
render at all?" -- which is what catches a typo in a {% url %} tag or a
variable that doesn't exist.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from listings.models import Category, Listing
from orders.models import Order

User = get_user_model()


class PageRenderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Vegetables')
        cls.farmer = User.objects.create_user(
            username='farmer', password='pw', role=User.Role.FARMER,
            first_name='Amina', last_name='Bello', location='Jos',
        )
        cls.buyer = User.objects.create_user(
            username='buyer', password='pw', role=User.Role.BUYER,
            first_name='Chidi', last_name='Nwosu', location='Enugu',
        )
        cls.listing = Listing.objects.create(
            farmer=cls.farmer, category=cls.category, title='Tomatoes',
            description='Fresh from the farm.', price=Decimal('1800.00'),
            unit='basket', quantity_available=24,
        )

    def assertRenders(self, url, status=200):
        response = self.client.get(url)
        self.assertEqual(
            response.status_code, status, f'{url} returned {response.status_code}'
        )
        return response

    # --- Public pages -------------------------------------------------------

    def test_public_pages(self):
        self.assertRenders(reverse('listings:list'))
        self.assertRenders(reverse('listings:detail', args=[self.listing.pk]))
        self.assertRenders(reverse('accounts:login'))
        self.assertRenders(reverse('accounts:register'))

    # --- Farmer pages -------------------------------------------------------

    def test_farmer_pages(self):
        self.client.force_login(self.farmer)
        self.assertRenders(reverse('listings:dashboard'))
        self.assertRenders(reverse('listings:create'))
        self.assertRenders(reverse('listings:update', args=[self.listing.pk]))
        self.assertRenders(reverse('listings:delete', args=[self.listing.pk]))
        self.assertRenders(reverse('orders:sales'))
        self.assertRenders(reverse('accounts:profile'))

    # --- Buyer pages --------------------------------------------------------

    def test_buyer_pages_with_a_full_cart_and_an_order(self):
        self.client.force_login(self.buyer)

        self.assertRenders(reverse('orders:cart'))  # empty state
        self.client.post(
            reverse('orders:add_to_cart', args=[self.listing.pk]), {'quantity': 2}
        )
        self.assertRenders(reverse('orders:cart'))  # populated
        self.assertRenders(reverse('orders:checkout'))

        self.client.post(
            reverse('orders:checkout'),
            {
                'delivery_address': '12 Market Road',
                'contact_phone': '08012345678',
                'note': 'Call ahead',
            },
        )
        order = Order.objects.get()

        self.assertRenders(reverse('orders:list'))
        self.assertRenders(order.get_absolute_url())
        self.assertRenders(reverse('accounts:profile'))

    def test_marketplace_filters_and_pagination_render(self):
        self.assertRenders(reverse('listings:list') + '?q=tomato')
        self.assertRenders(reverse('listings:list') + '?category=vegetables')
        self.assertRenders(reverse('listings:list') + '?sort=price_low')
        self.assertRenders(reverse('listings:list') + '?page=1&sort=price_high')

    def test_seller_sees_status_control_on_order_page(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse('orders:add_to_cart', args=[self.listing.pk]))
        self.client.post(
            reverse('orders:checkout'),
            {'delivery_address': 'Enugu', 'contact_phone': '0801', 'note': ''},
        )
        order = Order.objects.get()

        self.client.force_login(self.farmer)
        response = self.assertRenders(order.get_absolute_url())
        self.assertContains(response, 'Update status')
