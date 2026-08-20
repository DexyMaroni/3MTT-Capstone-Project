"""Cache-busting stamp for the static assets base.html pulls in.

The dev server sends `Last-Modified` but no `Cache-Control` or `ETag`, so
browsers fall back to heuristic caching: they reuse a stored copy of
main.css without asking whether it changed. Edit the stylesheet and the
page keeps rendering with the old rules until you force a hard refresh.

Appending `?v=<newest mtime>` puts the change in the URL itself, so a
normal refresh is enough -- the browser has no cached entry for the new
URL and has to fetch it.
"""

from pathlib import Path

from django.conf import settings

# Only the files base.html links. Widen this if you add more.
TRACKED_ASSETS = ('css/main.css', 'js/main.js')


def asset_version(request):
    newest = 0
    for root in settings.STATICFILES_DIRS:
        for relative_path in TRACKED_ASSETS:
            asset = Path(root) / relative_path
            if asset.exists():
                newest = max(newest, int(asset.stat().st_mtime))
    return {'ASSET_V': newest}
