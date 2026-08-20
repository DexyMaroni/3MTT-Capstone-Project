from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """A single user table with a role flag.

    We extend AbstractUser rather than adding a separate Profile model because
    every user here is either a farmer or a buyer -- there is no case where a
    user exists without a role, so a one-to-one profile would only add a join.
    """

    class Role(models.TextChoices):
        FARMER = 'FARMER', 'Farmer'
        BUYER = 'BUYER', 'Buyer'

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.BUYER,
        help_text='Farmers create listings; buyers place orders.',
    )
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(
        max_length=120,
        blank=True,
        help_text='Town or state, shown to buyers on your listings.',
    )

    @property
    def is_farmer(self) -> bool:
        return self.role == self.Role.FARMER

    @property
    def is_buyer(self) -> bool:
        return self.role == self.Role.BUYER

    def display_name(self) -> str:
        return self.get_full_name() or self.username

    def __str__(self) -> str:
        return f'{self.username} ({self.get_role_display()})'
