from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from listings.models import Category, Listing

from .models import Cart, CartItem, Order

User = get_user_model()


class CartTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Vegetables')
        self.farmer = User.objects.create_user(
            username='farmer', password='pw', role=User.Role.FARMER
        )
        self.buyer = User.objects.create_user(
            username='buyer', password='pw', role=User.Role.BUYER
        )
        self.listing = Listing.objects.create(
            farmer=self.farmer, category=self.category, title='Tomatoes',
            price=Decimal('1800.00'), quantity_available=10,
        )
        self.client.force_login(self.buyer)

    def test_adding_same_listing_twice_increases_quantity(self):
        url = reverse('orders:add_to_cart', args=[self.listing.pk])
        self.client.post(url, {'quantity': 2})
        self.client.post(url, {'quantity': 3})

        item = CartItem.objects.get(cart__buyer=self.buyer, listing=self.listing)
        self.assertEqual(item.quantity, 5)
        self.assertEqual(CartItem.objects.count(), 1)

    def test_quantity_is_capped_at_available_stock(self):
        self.client.post(
            reverse('orders:add_to_cart', args=[self.listing.pk]), {'quantity': 999}
        )
        item = CartItem.objects.get(cart__buyer=self.buyer)
        self.assertEqual(item.quantity, 10)

    def test_out_of_stock_listing_is_rejected(self):
        self.listing.quantity_available = 0
        self.listing.save()

        self.client.post(reverse('orders:add_to_cart', args=[self.listing.pk]))
        self.assertEqual(CartItem.objects.count(), 0)

    def test_cart_total_sums_line_subtotals(self):
        self.client.post(
            reverse('orders:add_to_cart', args=[self.listing.pk]), {'quantity': 3}
        )
        cart = Cart.objects.get(buyer=self.buyer)
        self.assertEqual(cart.total, Decimal('5400.00'))
        self.assertEqual(cart.item_count, 3)

    def test_ajax_add_returns_json(self):
        response = self.client.post(
            reverse('orders:add_to_cart', args=[self.listing.pk]),
            {'quantity': 1},
            headers={'x-requested-with': 'XMLHttpRequest'},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['cart_item_count'], 1)

    def test_ajax_add_describes_the_item_for_the_dialog(self):
        # The confirmation dialog reads these keys straight out of the
        # response, so removing one breaks the popup rather than any view.
        response = self.client.post(
            reverse('orders:add_to_cart', args=[self.listing.pk]),
            {'quantity': 2},
            headers={'x-requested-with': 'XMLHttpRequest'},
        )
        payload = response.json()

        self.assertFalse(payload['capped'])
        self.assertEqual(
            payload['item'],
            {
                'title': 'Tomatoes',
                'quantity': 2,
                # Plural, because the dialog says "2 kilograms", not
                # "2 kilogram" -- see Listing.unit_label().
                'unit': 'kilograms',
                'line_total': '3600.00',
                'image': '',
            },
        )
        self.assertEqual(payload['cart_total'], '3600.00')

    def test_unit_is_singular_for_a_quantity_of_one(self):
        response = self.client.post(
            reverse('orders:add_to_cart', args=[self.listing.pk]),
            {'quantity': 1},
            headers={'x-requested-with': 'XMLHttpRequest'},
        )
        self.assertEqual(response.json()['item']['unit'], 'kilogram')

    def test_ajax_add_reports_the_capped_quantity_not_the_requested_one(self):
        # Asking for more than exists must not leave the dialog claiming the
        # buyer got 999 of something.
        response = self.client.post(
            reverse('orders:add_to_cart', args=[self.listing.pk]),
            {'quantity': 999},
            headers={'x-requested-with': 'XMLHttpRequest'},
        )
        payload = response.json()

        self.assertTrue(payload['capped'])
        self.assertEqual(payload['item']['quantity'], 10)
        self.assertEqual(payload['item']['line_total'], '18000.00')
        self.assertIn('Only 10', payload['message'])

    def test_farmer_cannot_use_the_cart(self):
        self.client.force_login(self.farmer)
        response = self.client.get(reverse('orders:cart'))
        self.assertRedirects(response, reverse('listings:list'))

    def test_buyer_cannot_touch_another_buyers_cart_item(self):
        self.client.post(reverse('orders:add_to_cart', args=[self.listing.pk]))
        item = CartItem.objects.get()

        intruder = User.objects.create_user(
            username='intruder', password='pw', role=User.Role.BUYER
        )
        self.client.force_login(intruder)
        response = self.client.post(
            reverse('orders:update_item', args=[item.pk]), {'quantity': 99}
        )
        self.assertEqual(response.status_code, 404)


class CheckoutTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Grains')
        self.farmer = User.objects.create_user(
            username='farmer', password='pw', role=User.Role.FARMER
        )
        self.buyer = User.objects.create_user(
            username='buyer', password='pw', role=User.Role.BUYER
        )
        self.listing = Listing.objects.create(
            farmer=self.farmer, category=self.category, title='Ofada Rice',
            price=Decimal('3800.00'), quantity_available=10,
        )
        self.client.force_login(self.buyer)

    def _checkout(self):
        return self.client.post(
            reverse('orders:checkout'),
            {
                'delivery_address': '12 Market Road, Enugu',
                'contact_phone': '08012345678',
                'note': 'Call on arrival',
            },
        )

    def test_checkout_creates_order_and_empties_cart(self):
        self.client.post(
            reverse('orders:add_to_cart', args=[self.listing.pk]), {'quantity': 2}
        )
        response = self._checkout()

        order = Order.objects.get()
        self.assertRedirects(response, order.get_absolute_url())
        self.assertEqual(order.buyer, self.buyer)
        self.assertEqual(order.total_amount, Decimal('7600.00'))
        self.assertEqual(order.status, Order.Status.PENDING)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_checkout_decrements_stock(self):
        self.client.post(
            reverse('orders:add_to_cart', args=[self.listing.pk]), {'quantity': 4}
        )
        self._checkout()

        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity_available, 6)

    def test_order_item_snapshots_price_so_later_edits_dont_change_history(self):
        self.client.post(
            reverse('orders:add_to_cart', args=[self.listing.pk]), {'quantity': 1}
        )
        self._checkout()

        self.listing.price = Decimal('9999.00')
        self.listing.save()

        item = Order.objects.get().items.get()
        self.assertEqual(item.unit_price, Decimal('3800.00'))
        self.assertEqual(item.title, 'Ofada Rice')
        self.assertEqual(item.farmer, self.farmer)

    def test_checkout_is_blocked_when_stock_ran_out_first(self):
        self.client.post(
            reverse('orders:add_to_cart', args=[self.listing.pk]), {'quantity': 5}
        )
        # Someone else buys most of it between adding and checking out.
        Listing.objects.filter(pk=self.listing.pk).update(quantity_available=1)

        response = self._checkout()

        self.assertRedirects(response, reverse('orders:cart'))
        self.assertEqual(Order.objects.count(), 0)
        # The whole transaction rolled back, so stock is untouched.
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity_available, 1)

    def test_empty_cart_cannot_check_out(self):
        response = self.client.get(reverse('orders:checkout'))
        self.assertRedirects(response, reverse('listings:list'))

    def test_order_reference_is_unique_per_order(self):
        for _ in range(2):
            self.client.post(
                reverse('orders:add_to_cart', args=[self.listing.pk]), {'quantity': 1}
            )
            self._checkout()

        references = set(Order.objects.values_list('reference', flat=True))
        self.assertEqual(len(references), 2)


class OrderAccessTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Fruits')
        self.farmer = User.objects.create_user(
            username='farmer', password='pw', role=User.Role.FARMER
        )
        self.buyer = User.objects.create_user(
            username='buyer', password='pw', role=User.Role.BUYER
        )
        self.listing = Listing.objects.create(
            farmer=self.farmer, category=self.category, title='Pineapple',
            price=Decimal('900.00'), quantity_available=20,
        )
        self.client.force_login(self.buyer)
        self.client.post(
            reverse('orders:add_to_cart', args=[self.listing.pk]), {'quantity': 2}
        )
        self.client.post(
            reverse('orders:checkout'),
            {'delivery_address': 'Abuja', 'contact_phone': '0801', 'note': ''},
        )
        self.order = Order.objects.get()

    def test_seller_can_view_and_update_the_order(self):
        self.client.force_login(self.farmer)

        response = self.client.get(self.order.get_absolute_url())
        self.assertEqual(response.status_code, 200)

        self.client.post(
            reverse('orders:update_status', args=[self.order.pk]),
            {'status': Order.Status.SHIPPED},
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.SHIPPED)

    def test_unrelated_user_cannot_view_the_order(self):
        stranger = User.objects.create_user(
            username='stranger', password='pw', role=User.Role.BUYER
        )
        self.client.force_login(stranger)
        response = self.client.get(self.order.get_absolute_url())
        self.assertRedirects(response, reverse('listings:list'))

    def test_buyer_cannot_change_the_status(self):
        response = self.client.post(
            reverse('orders:update_status', args=[self.order.pk]),
            {'status': Order.Status.DELIVERED},
        )
        self.assertRedirects(response, reverse('listings:list'))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_invalid_status_is_rejected(self):
        self.client.force_login(self.farmer)
        self.client.post(
            reverse('orders:update_status', args=[self.order.pk]),
            {'status': 'TELEPORTED'},
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    def test_sales_page_shows_the_farmers_lines(self):
        self.client.force_login(self.farmer)
        response = self.client.get(reverse('orders:sales'))
        self.assertContains(response, 'Pineapple')
        self.assertContains(response, self.order.reference)
