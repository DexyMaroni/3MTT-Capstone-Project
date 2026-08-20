# FarmLink — Produce Marketplace

A marketplace where farmers list produce and buyers order it directly. Built with
Django, server-rendered HTML templates, hand-written CSS, and vanilla JavaScript.

**3MTT Capstone Project**

---

## What it does

**Farmers** create listings (produce, price per unit, quantity, photo), manage stock
from a dashboard, see every order containing their produce, and move orders through
`Pending → Confirmed → Shipped → Delivered`.

**Buyers** browse and search the marketplace, filter by category, sort by price,
add produce to a cart, check out with delivery details, and track order status.

**Admins** manage users, listings and orders through the Django admin at `/admin/`.

---

## Running it

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Build the database, load demo data, attach the photos
python manage.py setup_demo

# 4. Start the server
python manage.py runserver
```

Open http://127.0.0.1:8000/

**No internet connection is needed.** The sixteen produce photos are committed
under `listings/seed_images/`, and `setup_demo` copies them in. Everything runs
from the repository as cloned.

`setup_demo` is safe to re-run — it will not duplicate anything. It is just
these three in the required order:

```bash
python manage.py migrate       # create the tables
python manage.py seed_demo     # categories, users, 16 listings
python manage.py load_images   # attach the bundled photos
```

To start over from nothing, delete `db.sqlite3` and `media/`, then run
`setup_demo` again.

### Where the photos come from

`media/` is runtime upload territory and stays out of git. The demo photos live
in `listings/seed_images/` with a `manifest.json` recording each one's
photographer, licence and description.

Two commands manage them:

| Command | Needs internet | What it does |
| ------- | -------------- | ------------ |
| `load_images`  | No  | Copies the committed photos into `media/`. This is what setup uses. |
| `fetch_images` | Yes | Re-downloads the originals from Wikimedia Commons, crops them to 4:3 at 1200×900, and rebuilds the seed set. |

They are Creative Commons images, and CC BY / CC BY-SA require attribution —
which is why a credit line appears under each photo on its detail page.

### Demo accounts

`seed_demo` creates these, all with the password **`farmlink123`**:

| Role   | Usernames                                  |
| ------ | ------------------------------------------ |
| Farmer | `amina_farms`, `okon_greens`, `tunde_agro` |
| Buyer  | `chidi_buys`, `grace_market`               |
| Admin  | `admin`                                    |

### Running the tests

```bash
python manage.py test
```

---

## How the project is laid out

```
manage.py                 Django's command-line entry point
produce_market/           Project config
  settings.py             Installed apps, database, templates, auth
  urls.py                 Top-level URL routing
accounts/                 Users and authentication
  models.py               Custom User with a farmer/buyer role
  decorators.py           @farmer_required / @buyer_required
listings/                 Produce catalogue
  models.py               Category, Listing
  views.py                Marketplace grid, detail page, farmer dashboard/CRUD
  seed_images/            The 16 demo photos + manifest.json (credits, alt text)
  management/commands/    setup_demo, seed_demo, load_images, fetch_images
orders/                   Cart and checkout
  models.py               Cart, CartItem, Order, OrderItem
  views.py                Cart operations, checkout, order tracking
  context_processors.py   Cart badge count for every page
templates/                base.html and shared partials
static/css/main.css       All styling
static/js/main.js         Cart AJAX, quantity steppers, live subtotals
tests_smoke.py            Renders every page as the role meant to see it
```

---

## Design decisions worth understanding

These are the choices that took the most thought — they're the parts worth being
able to explain when the project is assessed.

### One user table, with a role field

`accounts.User` extends `AbstractUser` and adds `role`, `phone` and `location`.
The alternative — a separate `Profile` model linked one-to-one — is common, but
here every user *must* be either a farmer or a buyer, so a profile row would exist
for every user anyway and only add a join to every query.

`AUTH_USER_MODEL` was set *before* the first migration. Changing it afterwards is
genuinely painful, which is why it's worth getting right at the start.

### Orders store copies, not references

`OrderItem` saves `title`, `unit_price`, `unit` and `farmer` directly onto the row
rather than reading them from the listing later. This matters: if a farmer raises
a price next week, last week's order must still show what the buyer actually paid.
The `listing` foreign key uses `on_delete=SET_NULL`, so deleting a listing never
destroys order history.

`Order.total_amount` is stored for the same reason.

### Checkout is one transaction

`orders/views.py::_place_order` wraps the whole checkout in
`transaction.atomic()`. Inside it:

1. Listing rows are locked with `select_for_update()`.
2. Stock is re-checked — the cart might be minutes old.
3. The order and its items are written.
4. Stock is decremented with `F('quantity_available') - quantity`, so the
   subtraction happens in SQL and can't use a stale value.

If any check fails, nothing is written at all. Two buyers racing for the last crate
can't both succeed.

### Permission checks that can't be forgotten

Instead of fetching a listing and *then* checking who owns it, the edit and delete
views scope the lookup itself:

```python
listing = get_object_or_404(Listing, pk=pk, farmer=request.user)
```

Another farmer's listing simply isn't found. The check can't be skipped, because
it *is* the query.

### JavaScript as enhancement, not requirement

Every interactive feature is a real HTML form first. `static/js/main.js` intercepts
the submit and sends it with `fetch()` instead — and if the request fails, it calls
`form.submit()` to fall back to a normal page load. Turn JavaScript off entirely and
the whole site still works.

The views detect this with the `X-Requested-With` header and return JSON or a
redirect accordingly.

### Query efficiency

`ListingQuerySet` (in `listings/models.py`) holds reusable filters. `.with_related()`
adds `select_related('farmer', 'category')` so rendering a 9-card grid is one query
rather than nineteen. The farmer dashboard's revenue figure is a single aggregate
query using `Sum(F('unit_price') * F('quantity'))` rather than a Python loop.

---

## Things you could add next

- Product reviews and farmer ratings
- Real payment integration (Paystack or Flutterwave)
- Email notifications when an order status changes
- Delivery fee calculation based on distance
- Farmer analytics — best-selling produce, revenue over time
- A REST API so a mobile app could use the same backend

---

## Notes for deployment

Setting `DJANGO_DEBUG=False` turns on the HTTPS-only settings automatically —
SSL redirect, secure session and CSRF cookies, and HSTS. They are off in
development because the dev server speaks plain HTTP, and a secure-only cookie
would never be sent back.

Required environment variables:

| Variable                        | Purpose                                       |
| ------------------------------- | --------------------------------------------- |
| `DJANGO_SECRET_KEY`             | Signs sessions and tokens. **Required** when `DEBUG=False` — startup fails otherwise, rather than quietly signing with the public development key. |
| `DJANGO_DEBUG`                  | `False` in production                          |
| `DJANGO_ALLOWED_HOSTS`          | Comma-separated hostnames                      |
| `DJANGO_CSRF_TRUSTED_ORIGINS`   | Comma-separated `https://` origins             |
| `DJANGO_HSTS_SECONDS`           | Defaults to one year — start at `3600` and raise it once HTTPS is confirmed working, because browsers cache this header and it cannot be withdrawn early |
| `EMAIL_HOST` / `EMAIL_PORT` / `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` | SMTP; the console backend is development-only |

Behind a reverse proxy, `SECURE_PROXY_SSL_HEADER` is already set to trust
`X-Forwarded-Proto`. Without it Django only sees the internal HTTP hop and
`SECURE_SSL_REDIRECT` loops forever.

Also:

- Switch `DATABASES` to PostgreSQL. `select_for_update()` in checkout is a
  genuine row-level lock there; SQLite has no row-level locking and serialises
  writers at the database level instead.
- Run `python manage.py collectstatic` and serve `staticfiles/` and `media/`
  from a real web server rather than Django.
- Move uploaded media to object storage — `media/` on a single container's disk
  disappears on redeploy.
