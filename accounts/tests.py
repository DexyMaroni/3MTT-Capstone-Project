from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class RegistrationTests(TestCase):
    def _payload(self, **overrides):
        data = {
            'username': 'newuser',
            'email': 'new@example.com',
            'role': User.Role.BUYER,
            'phone': '08012345678',
            'location': 'Kano',
            'password1': 'Str0ngPassw0rd!',
            'password2': 'Str0ngPassw0rd!',
        }
        data.update(overrides)
        return data

    def test_buyer_signup_logs_in_and_lands_on_marketplace(self):
        response = self.client.post(reverse('accounts:register'), self._payload())
        self.assertRedirects(response, reverse('listings:list'))

        user = User.objects.get(username='newuser')
        self.assertTrue(user.is_buyer)
        self.assertEqual(self.client.session['_auth_user_id'], str(user.pk))

    def test_farmer_signup_lands_on_dashboard(self):
        response = self.client.post(
            reverse('accounts:register'),
            self._payload(username='newfarmer', role=User.Role.FARMER),
        )
        self.assertRedirects(response, reverse('listings:dashboard'))
        self.assertTrue(User.objects.get(username='newfarmer').is_farmer)

    def test_mismatched_passwords_are_rejected(self):
        response = self.client.post(
            reverse('accounts:register'), self._payload(password2='different')
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_role_defaults_to_buyer(self):
        user = User.objects.create_user(username='plain', password='pw')
        self.assertTrue(user.is_buyer)

    def test_duplicate_username_is_a_form_error(self):
        User.objects.create_user(username='newuser', password='pw')

        response = self.client.post(reverse('accounts:register'), self._payload())

        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)
        self.assertEqual(User.objects.filter(username='newuser').count(), 1)

    def test_username_taken_during_the_request_is_not_a_500(self):
        # Hashing the password takes over a second, so a double-submitted
        # form can land a second request between this one's uniqueness check
        # and its INSERT. Both pass validation; the database decides. Standing
        # in for that timing here: the form validates, then saving raises the
        # constraint error the loser would really get.
        with mock.patch(
            'accounts.forms.RegistrationForm.save',
            side_effect=IntegrityError('UNIQUE constraint failed: accounts_user.username'),
        ):
            response = self.client.post(reverse('accounts:register'), self._payload())

        self.assertEqual(response.status_code, 200)
        self.assertIn('username', response.context['form'].errors)
        self.assertNotIn('_auth_user_id', self.client.session)


class ProfileTests(TestCase):
    def test_profile_requires_login(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_user_can_update_their_details(self):
        user = User.objects.create_user(username='u', password='pw')
        self.client.force_login(user)

        self.client.post(
            reverse('accounts:profile'),
            {
                'first_name': 'Grace', 'last_name': 'Ekpo',
                'email': 'grace@example.com', 'phone': '08099999999',
                'location': 'Abuja',
            },
        )
        user.refresh_from_db()
        self.assertEqual(user.display_name(), 'Grace Ekpo')
        self.assertEqual(user.location, 'Abuja')
