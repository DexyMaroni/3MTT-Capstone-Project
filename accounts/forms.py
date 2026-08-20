from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class RegistrationForm(UserCreationForm):
    """Sign-up form that also asks which side of the market you're on."""

    email = forms.EmailField(required=True)
    role = forms.ChoiceField(
        choices=User.Role.choices,
        widget=forms.RadioSelect,
        initial=User.Role.BUYER,
        label='I want to',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'email', 'role', 'phone', 'location']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['location'].widget.attrs['placeholder'] = 'e.g. Jos, Plateau'
        self.fields['phone'].widget.attrs['placeholder'] = 'e.g. 08012345678'
        # The radio buttons read better with verbs than with bare role names.
        self.fields['role'].choices = [
            (User.Role.BUYER, 'Buy produce'),
            (User.Role.FARMER, 'Sell my produce'),
        ]


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'location']
