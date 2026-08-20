from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def farmer_required(view_func):
    """Allow only signed-in farmers through.

    Anonymous users are sent to log in; signed-in buyers get a message rather
    than a bare 403, since hitting this usually means they followed a stale link.
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{'/accounts/login/'}?next={request.path}")
        if not request.user.is_farmer:
            messages.error(request, 'That page is for farmer accounts only.')
            return redirect('listings:list')
        return view_func(request, *args, **kwargs)

    return _wrapped


def buyer_required(view_func):
    """Allow only signed-in buyers through (cart, checkout, order history)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{'/accounts/login/'}?next={request.path}")
        if not request.user.is_buyer:
            messages.error(request, 'Only buyer accounts can place orders.')
            return redirect('listings:list')
        return view_func(request, *args, **kwargs)

    return _wrapped
