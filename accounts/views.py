from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render

from .forms import ProfileForm, RegistrationForm


def register(request):
    if request.user.is_authenticated:
        return redirect('listings:list')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                # Hashing a password takes over a second, which leaves a wide
                # gap between the form's "is this username free?" SELECT and
                # the INSERT. A double-submitted form can slip a second
                # request into that gap, and both pass validation. The unique
                # constraint is what actually decides it, so treat losing that
                # race as a validation error rather than a 500.
                #
                # atomic() matters here: without it the failed INSERT leaves a
                # broken transaction that poisons every later query on
                # PostgreSQL, even though SQLite tolerates it.
                with transaction.atomic():
                    user = form.save()
            except IntegrityError:
                form.add_error(
                    'username',
                    'That username was taken a moment ago. Please pick another.',
                )
            else:
                # Log them straight in -- asking someone to sign in immediately
                # after signing up is a needless extra step.
                login(request, user)
                messages.success(request, f'Welcome, {user.display_name()}!')
                return redirect(
                    'listings:dashboard' if user.is_farmer else 'listings:list'
                )
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated.')
            return redirect('accounts:profile')
    else:
        form = ProfileForm(instance=request.user)

    return render(request, 'accounts/profile.html', {'form': form})
