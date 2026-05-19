/* nav_user.js — shared navbar profile logic for all pages */
document.addEventListener('DOMContentLoaded', function () {

  /* populate name/email from session */
  var u = JSON.parse(localStorage.getItem('qc_user') || 'null');
  if (u) {
    var init = (u.name || 'U').charAt(0).toUpperCase();
    var av = document.getElementById('navAvatar');
    if (av) av.src = 'https://ui-avatars.com/api/?name=' + encodeURIComponent(init) + '&background=6366f1&color=fff&rounded=true';
    var pn = document.getElementById('pmName');  if (pn) pn.textContent = u.name  || 'User';
    var pe = document.getElementById('pmEmail'); if (pe) pe.textContent = u.email || '';
  }

  /* toggle dropdown on avatar click */
  var av2 = document.getElementById('navAvatar');
  var pm  = document.getElementById('profileMenu');
  if (av2 && pm) {
    av2.addEventListener('click', function (e) {
      e.stopPropagation();
      pm.classList.toggle('open');
    });
    document.addEventListener('click', function () {
      pm.classList.remove('open');
    });
  }

  /* sign out */
  var so = document.getElementById('navSignOut');
  if (so) {
    so.addEventListener('click', function (e) {
      e.preventDefault();
      zynConfirm({
        icon: 'danger',
        title: 'Sign Out',
        message: 'Are you sure you want to sign out of ZYNAPSE?',
        confirmText: 'Yes, Sign Out',
        cancelText: 'Cancel',
        btnStyle: 'confirm-danger'
      }).then(function (yes) {
        if (yes) {
          localStorage.clear();
          window.location.replace('/login.html');
        }
      });
    });
  }

  /* Update Cart Badge Count */
  var cartCount = document.getElementById('navCartCount');
  if (cartCount) {
    var cart = JSON.parse(localStorage.getItem('qc_cart') || '[]');
    if (cart.length > 0) {
      cartCount.style.display = 'block';
      cartCount.textContent = cart.length;
    } else {
      cartCount.style.display = 'none';
    }
  }

});
