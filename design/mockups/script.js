/* Menu (phone) and contact form behaviour of the mockup. */
(function () {
  var btn = document.querySelector('.menu-btn');
  var nav = document.getElementById('site-nav');
  if (btn && nav) {
    var setOpen = function (open) {
      nav.classList.toggle('is-open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    };
    btn.addEventListener('click', function () {
      setOpen(!nav.classList.contains('is-open'));
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && nav.classList.contains('is-open')) {
        setOpen(false);
        btn.focus();
      }
    });
  }

  var form = document.querySelector('[data-contact-form]');
  if (!form) return;

  var MESSAGES = {
    vorname: 'Bitte gib deinen Vornamen an.',
    nachname: 'Bitte gib deinen Nachnamen an.',
    email: 'Bitte gib deine Email-Adresse an.',
    emailInvalid: 'Diese Email-Adresse sieht nicht gültig aus.',
    nachricht: 'Bitte schreib uns eine Nachricht.',
    nachrichtLong: 'Die Nachricht darf höchstens 5000 Zeichen lang sein.'
  };
  var EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

  function check(name, raw) {
    var v = (raw || '').trim();
    if (!v) return MESSAGES[name];
    if (name === 'email' && !EMAIL.test(v)) return MESSAGES.emailInvalid;
    if (name === 'nachricht' && v.length > 5000) return MESSAGES.nachrichtLong;
    return '';
  }

  var fields = ['vorname', 'nachname', 'email', 'nachricht'].map(function (n) {
    return form.elements[n];
  });

  function show(input, msg) {
    var err = document.getElementById(input.id + '-error');
    if (!err) return;
    var text = err.querySelector('span');
    if (msg) {
      input.setAttribute('aria-invalid', 'true');
      if (text) text.textContent = msg;
      err.hidden = false;
    } else {
      input.removeAttribute('aria-invalid');
      err.hidden = true;
    }
  }

  fields.forEach(function (input) {
    input.addEventListener('input', function () {
      input.dataset.dirty = '1';
      if (input.getAttribute('aria-invalid')) show(input, check(input.name, input.value));
    });
    input.addEventListener('blur', function () {
      if (input.dataset.dirty) show(input, check(input.name, input.value));
    });
  });

  var submit = form.querySelector('[type="submit"]');
  var thanks = document.querySelector('[data-contact-thanks]');
  var alertBox = form.querySelector('[data-form-alert]');

  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var first = null;
    fields.forEach(function (input) {
      var msg = check(input.name, input.value);
      show(input, msg);
      if (msg && !first) first = input;
    });
    if (first) { first.focus(); return; }
    if (alertBox) alertBox.hidden = true;
    submit.disabled = true;
    submit.classList.add('is-sending');
    submit.querySelector('span').textContent = 'Wird gesendet …';
    window.setTimeout(function () {
      form.hidden = true;
      if (thanks) {
        thanks.hidden = false;
        thanks.setAttribute('tabindex', '-1');
        thanks.focus();
      }
    }, 1900);
  });
})();
