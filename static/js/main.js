/* FarmLink front-end behaviour.
 *
 * Everything here is progressive enhancement: each feature upgrades a form
 * that already works on its own. Turn JavaScript off and the site still
 * functions -- it just does full page reloads.
 */

(function () {
  'use strict';

  /** Django requires the CSRF token on every unsafe request. */
  function getCsrfToken(form) {
    var input = form.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  /** POST a form in the background and return the parsed JSON response. */
  function postForm(form) {
    return fetch(form.action, {
      method: 'POST',
      headers: {
        // Our views check this header to decide between JSON and a redirect.
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRFToken': getCsrfToken(form)
      },
      body: new FormData(form)
    }).then(function (response) {
      return response.json().then(function (data) {
        return { ok: response.ok, data: data };
      });
    });
  }

  /** Update every cart badge on the page. */
  function setCartCount(count) {
    document.querySelectorAll('[data-cart-count]').forEach(function (el) {
      el.textContent = count;
    });
  }

  /** How long a toast stays on screen. */
  var TOAST_MS = 4500;

  /** Fade a toast out, then take it out of the DOM. */
  function dismiss(toast) {
    if (toast.dataset.leaving) { return; }   // already on its way out
    toast.dataset.leaving = '1';
    toast.classList.add('message-leaving');
    setTimeout(function () { toast.remove(); }, 300);
  }

  /** Give a toast its dismiss timer, and let a click close it early. */
  function armToast(toast) {
    toast.addEventListener('click', function () { dismiss(toast); });
    setTimeout(function () { dismiss(toast); }, TOAST_MS);
  }

  /** Show a transient toast. Used for everything except adding to cart,
   *  which gets the confirmation dialog below instead. */
  function flash(text, kind) {
    // base.html always renders this region, even with no server messages,
    // so there is nothing to build here.
    var list = document.querySelector('[data-messages]');
    if (!list) { return; }

    var toast = document.createElement('li');
    toast.className = 'message message-' + (kind || 'success');
    toast.textContent = text;
    list.appendChild(toast);
    armToast(toast);
  }

  /* --- Add-to-cart confirmation dialog ------------------------------------ */

  var dialog = document.querySelector('[data-cart-dialog]');

  /** Fill the dialog from the server's response and open it.
   *  Returns false if the browser has no <dialog> support, so the caller
   *  can fall back to a toast. */
  function showCartDialog(data) {
    if (!dialog || typeof dialog.showModal !== 'function') { return false; }

    var item = data.item || {};

    var image = dialog.querySelector('[data-dialog-image]');
    if (item.image) {
      image.src = item.image;
      image.hidden = false;
    } else {
      image.removeAttribute('src');
      image.hidden = true;
    }

    dialog.querySelector('[data-dialog-name]').textContent = item.title || '';
    dialog.querySelector('[data-dialog-line]').textContent =
      item.quantity + ' ' + item.unit + ' · ₦' + item.line_total;
    dialog.querySelector('[data-dialog-total]').textContent = '₦' + data.cart_total;

    // Only shown when the cart was trimmed to the stock actually available.
    var note = dialog.querySelector('[data-dialog-note]');
    note.hidden = !data.capped;
    note.textContent = data.capped ? data.message : '';

    dialog.showModal();
    return true;
  }

  if (dialog) {
    // Clicking the dark area outside the dialog closes it. The backdrop is
    // not a separate element, so a click on <dialog> itself means the
    // pointer landed outside the box.
    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) { dialog.close(); }
    });
  }

  /* --- Add to cart without leaving the page ------------------------------- */

  document.querySelectorAll('.add-to-cart-form').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      event.preventDefault();

      var button = form.querySelector('button[type=submit]');
      var originalText = button.textContent;
      button.disabled = true;
      button.textContent = 'Adding...';

      postForm(form)
        .then(function (result) {
          if (result.ok && result.data.ok) {
            setCartCount(result.data.cart_item_count);
            // Dialog where supported; toast on older browsers.
            if (!showCartDialog(result.data)) {
              flash(result.data.message, 'success');
            }
            button.textContent = 'Added';
            setTimeout(function () { button.textContent = originalText; }, 1500);
          } else {
            flash(result.data.message || 'Could not add that to your cart.', 'error');
            button.textContent = originalText;
          }
        })
        .catch(function () {
          // Network failure -- fall back to a normal submit so the user
          // still gets somewhere useful.
          form.submit();
        })
        .finally(function () {
          button.disabled = false;
        });
    });
  });

  /* --- Quantity steppers on the detail page ------------------------------- */

  document.querySelectorAll('[data-stepper]').forEach(function (stepper) {
    var input = stepper.querySelector('input[type=number]');

    stepper.querySelectorAll('button[data-step]').forEach(function (button) {
      button.addEventListener('click', function () {
        var step = parseInt(button.dataset.step, 10);
        var max = parseInt(input.max, 10) || Infinity;
        var min = parseInt(input.min, 10) || 1;
        var next = (parseInt(input.value, 10) || min) + step;

        input.value = Math.min(max, Math.max(min, next));
        input.dispatchEvent(new Event('input', { bubbles: true }));
      });
    });
  });

  /* --- Live subtotal preview ---------------------------------------------- */

  var preview = document.querySelector('.subtotal-preview');
  if (preview) {
    var target = preview.querySelector('[data-subtotal]');
    var unitPrice = parseFloat(preview.dataset.price);
    var qtyInput = document.querySelector('[data-stepper] input[type=number]');

    if (qtyInput && !isNaN(unitPrice)) {
      qtyInput.addEventListener('input', function () {
        var quantity = parseInt(qtyInput.value, 10) || 0;
        target.textContent = '₦' + (unitPrice * quantity).toFixed(2);
      });
    }
  }

  /* --- Cart quantity changes ---------------------------------------------- */

  document.querySelectorAll('.quantity-form').forEach(function (form) {
    var input = form.querySelector('input[type=number]');
    var timer;

    input.addEventListener('input', function () {
      // Wait for typing to settle so holding a spinner doesn't fire a
      // request per keystroke.
      clearTimeout(timer);
      timer = setTimeout(function () {
        postForm(form)
          .then(function (result) {
            if (!result.ok || !result.data.ok) { return; }

            var row = form.closest('[data-cart-row]');
            if (result.data.quantity === 0) {
              row.remove();
            } else {
              input.value = result.data.quantity;
              row.querySelector('[data-subtotal]').textContent =
                '₦' + result.data.subtotal;
            }

            setCartCount(result.data.cart_item_count);
            var total = document.querySelector('[data-cart-total]');
            if (total) { total.textContent = result.data.cart_total; }
          })
          .catch(function () { form.submit(); });
      }, 400);
    });
  });

  /* --- Sort dropdown submits itself ---------------------------------------- */

  document.querySelectorAll('[data-autosubmit] select').forEach(function (select) {
    select.addEventListener('change', function () {
      select.form.submit();
    });
  });

  /* --- Stop forms being submitted twice ------------------------------------ */

  /* Signing up and logging in spend over a second hashing the password, and
     checkout writes an order. That is long enough for a second click to open
     a parallel request. The server handles the collision on its own, but
     refusing to send the second request is friendlier -- and it stops
     checkout from being submitted twice. */
  document.querySelectorAll('form[method=post], form[method=POST]').forEach(function (form) {
    // These two are handled by fetch() above and never navigate away.
    if (form.classList.contains('add-to-cart-form') ||
        form.classList.contains('quantity-form')) {
      return;
    }

    form.addEventListener('submit', function (event) {
      if (form.dataset.submitting) {
        event.preventDefault();
        return;
      }
      form.dataset.submitting = '1';

      var button = form.querySelector('button[type=submit], button:not([type])');
      if (!button) { return; }

      // Disabling on the next tick, not now: a disabled control is dropped
      // from the submission, so doing it immediately would lose the value of
      // a named submit button (the order status buttons rely on theirs).
      setTimeout(function () { button.disabled = true; }, 0);
    });
  });

  /* Coming back via the Back button can restore the page from the cache with
     its buttons still disabled, which looks broken. Re-enable them. */
  window.addEventListener('pageshow', function (event) {
    if (!event.persisted) { return; }
    document.querySelectorAll('form[data-submitting]').forEach(function (form) {
      delete form.dataset.submitting;
      form.querySelectorAll('button[disabled]').forEach(function (button) {
        button.disabled = false;
      });
    });
  });

  /* --- Auto-dismiss server-rendered messages ------------------------------- */

  // Server-rendered messages behave exactly like JS-created ones.
  document.querySelectorAll('[data-messages] .message').forEach(armToast);
})();
