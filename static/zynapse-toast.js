/* ═══════════════════════════════════════════════════════════════
   ZYNAPSE — Premium Toast & Modal System
   Replaces all browser alert() / confirm() with beautiful UI
   ═══════════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  /* ── CSS injection ── */
  var style = document.createElement('style');
  style.textContent = `
    /* ═══════ TOAST CONTAINER ═══════ */
    .zyn-toast-container {
      position: fixed;
      top: 20px;
      right: 20px;
      z-index: 99999;
      display: flex;
      flex-direction: column;
      gap: 10px;
      pointer-events: none;
    }

    /* ═══════ TOAST ═══════ */
    .zyn-toast {
      pointer-events: auto;
      min-width: 340px;
      max-width: 440px;
      background: rgba(15, 23, 42, 0.85);
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 14px;
      padding: 16px 20px 14px;
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 0 0 1px rgba(255,255,255,0.05) inset;
      color: #fff;
      display: flex;
      flex-direction: column;
      gap: 8px;
      transform: translateX(120%);
      opacity: 0;
      transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.4s ease;
    }
    .zyn-toast.show {
      transform: translateX(0);
      opacity: 1;
    }
    .zyn-toast.exit {
      transform: translateX(120%);
      opacity: 0;
    }

    .zyn-toast-top {
      display: flex;
      align-items: flex-start;
      gap: 12px;
    }

    .zyn-toast-icon {
      width: 36px;
      height: 36px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.1rem;
      flex-shrink: 0;
    }
    .zyn-toast-icon.success { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
    .zyn-toast-icon.error   { background: rgba(239, 68, 68, 0.15); color: #f87171; }
    .zyn-toast-icon.warning { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
    .zyn-toast-icon.info    { background: rgba(99, 102, 241, 0.15); color: #a5b4fc; }

    .zyn-toast-body {
      flex: 1;
      min-width: 0;
    }
    .zyn-toast-title {
      font-weight: 700;
      font-size: 0.88rem;
      margin-bottom: 2px;
      line-height: 1.3;
    }
    .zyn-toast-msg {
      font-size: 0.8rem;
      color: rgba(255,255,255,0.6);
      line-height: 1.4;
    }

    .zyn-toast-close {
      background: none;
      border: none;
      color: rgba(255,255,255,0.4);
      font-size: 1.1rem;
      cursor: pointer;
      padding: 0;
      line-height: 1;
      transition: color 0.2s;
      flex-shrink: 0;
    }
    .zyn-toast-close:hover { color: #fff; }

    /* progress bar */
    .zyn-toast-progress {
      width: 100%;
      height: 3px;
      background: rgba(255,255,255,0.08);
      border-radius: 99px;
      overflow: hidden;
    }
    .zyn-toast-progress-bar {
      height: 100%;
      border-radius: 99px;
      transition: width linear;
    }
    .zyn-toast-progress-bar.success { background: #4ade80; }
    .zyn-toast-progress-bar.error   { background: #f87171; }
    .zyn-toast-progress-bar.warning { background: #fbbf24; }
    .zyn-toast-progress-bar.info    { background: #a5b4fc; }

    /* ═══════ CONFIRM MODAL ═══════ */
    .zyn-modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.6);
      backdrop-filter: blur(4px);
      -webkit-backdrop-filter: blur(4px);
      z-index: 99998;
      display: flex;
      align-items: center;
      justify-content: center;
      opacity: 0;
      transition: opacity 0.25s ease;
    }
    .zyn-modal-overlay.show { opacity: 1; }

    .zyn-modal {
      background: rgba(15, 23, 42, 0.92);
      backdrop-filter: blur(32px);
      -webkit-backdrop-filter: blur(32px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 18px;
      padding: 32px;
      width: 100%;
      max-width: 400px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255,255,255,0.05) inset;
      color: #fff;
      text-align: center;
      transform: scale(0.9) translateY(20px);
      transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .zyn-modal-overlay.show .zyn-modal {
      transform: scale(1) translateY(0);
    }

    .zyn-modal-icon {
      width: 56px;
      height: 56px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 1.5rem;
      margin: 0 auto 16px;
    }
    .zyn-modal-icon.danger  { background: rgba(239, 68, 68, 0.15); color: #f87171; }
    .zyn-modal-icon.warning { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
    .zyn-modal-icon.info    { background: rgba(99, 102, 241, 0.15); color: #a5b4fc; }

    .zyn-modal-title {
      font-weight: 800;
      font-size: 1.1rem;
      margin-bottom: 8px;
    }
    .zyn-modal-message {
      font-size: 0.875rem;
      color: rgba(255,255,255,0.55);
      margin-bottom: 24px;
      line-height: 1.5;
    }

    .zyn-modal-actions {
      display: flex;
      gap: 10px;
      justify-content: center;
    }

    .zyn-modal-btn {
      padding: 10px 24px;
      border-radius: 10px;
      font-weight: 700;
      font-size: 0.875rem;
      cursor: pointer;
      border: none;
      transition: all 0.2s;
    }
    .zyn-modal-btn.cancel {
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      color: rgba(255,255,255,0.7);
    }
    .zyn-modal-btn.cancel:hover {
      background: rgba(255,255,255,0.1);
      color: #fff;
    }
    .zyn-modal-btn.confirm-danger {
      background: #ef4444;
      color: #fff;
    }
    .zyn-modal-btn.confirm-danger:hover {
      background: #dc2626;
    }
    .zyn-modal-btn.confirm-primary {
      background: #6366f1;
      color: #fff;
    }
    .zyn-modal-btn.confirm-primary:hover {
      background: #4f46e5;
    }
    .zyn-modal-btn.confirm-success {
      background: #22c55e;
      color: #fff;
    }
    .zyn-modal-btn.confirm-success:hover {
      background: #16a34a;
    }
  `;
  document.head.appendChild(style);

  /* ── Create toast container ── */
  var container = document.createElement('div');
  container.className = 'zyn-toast-container';
  document.body.appendChild(container);

  /* ── Icon map ── */
  var icons = {
    success: '<i class="bi bi-check-circle-fill"></i>',
    error:   '<i class="bi bi-exclamation-triangle-fill"></i>',
    warning: '<i class="bi bi-exclamation-circle-fill"></i>',
    info:    '<i class="bi bi-info-circle-fill"></i>'
  };

  var titles = {
    success: 'Success',
    error:   'Error',
    warning: 'Warning',
    info:    'Notice'
  };

  /* ══════════════════════════════════════
     zynToast(options)
     ══════════════════════════════════════ */
  window.zynToast = function (opts) {
    if (typeof opts === 'string') {
      opts = { message: opts };
    }
    var type     = opts.type     || 'success';
    var title    = opts.title    || titles[type];
    var message  = opts.message  || '';
    var duration = opts.duration || 4000;

    var toast = document.createElement('div');
    toast.className = 'zyn-toast';
    toast.innerHTML =
      '<div class="zyn-toast-top">' +
        '<div class="zyn-toast-icon ' + type + '">' + icons[type] + '</div>' +
        '<div class="zyn-toast-body">' +
          '<div class="zyn-toast-title">' + title + '</div>' +
          '<div class="zyn-toast-msg">' + message + '</div>' +
        '</div>' +
        '<button class="zyn-toast-close">&times;</button>' +
      '</div>' +
      '<div class="zyn-toast-progress">' +
        '<div class="zyn-toast-progress-bar ' + type + '" style="width:100%"></div>' +
      '</div>';

    container.appendChild(toast);

    // slide in
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        toast.classList.add('show');
      });
    });

    // progress bar countdown
    var bar = toast.querySelector('.zyn-toast-progress-bar');
    requestAnimationFrame(function () {
      bar.style.transitionDuration = duration + 'ms';
      bar.style.width = '0%';
    });

    // close handler
    var closeBtn = toast.querySelector('.zyn-toast-close');
    var timer;

    function dismiss() {
      clearTimeout(timer);
      toast.classList.remove('show');
      toast.classList.add('exit');
      setTimeout(function () {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 400);
    }

    closeBtn.addEventListener('click', dismiss);

    timer = setTimeout(dismiss, duration);
  };

  /* ══════════════════════════════════════
     zynConfirm(options) → returns Promise
     ══════════════════════════════════════ */
  window.zynConfirm = function (opts) {
    if (typeof opts === 'string') {
      opts = { message: opts };
    }

    var iconType   = opts.icon       || 'danger';
    var title      = opts.title      || 'Are you sure?';
    var message    = opts.message     || '';
    var confirmTxt = opts.confirmText || 'Confirm';
    var cancelTxt  = opts.cancelText  || 'Cancel';
    var btnStyle   = opts.btnStyle    || 'confirm-danger';

    return new Promise(function (resolve) {
      var overlay = document.createElement('div');
      overlay.className = 'zyn-modal-overlay';
      overlay.innerHTML =
        '<div class="zyn-modal">' +
          '<div class="zyn-modal-icon ' + iconType + '">' + (icons[iconType === 'danger' ? 'error' : iconType] || icons.warning) + '</div>' +
          '<div class="zyn-modal-title">' + title + '</div>' +
          '<div class="zyn-modal-message">' + message + '</div>' +
          '<div class="zyn-modal-actions">' +
            '<button class="zyn-modal-btn cancel">' + cancelTxt + '</button>' +
            '<button class="zyn-modal-btn ' + btnStyle + '">' + confirmTxt + '</button>' +
          '</div>' +
        '</div>';

      document.body.appendChild(overlay);

      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          overlay.classList.add('show');
        });
      });

      function close(result) {
        overlay.classList.remove('show');
        setTimeout(function () {
          if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
          resolve(result);
        }, 250);
      }

      overlay.querySelector('.cancel').addEventListener('click', function () { close(false); });
      overlay.querySelector('.' + btnStyle).addEventListener('click', function () { close(true); });
      overlay.addEventListener('click', function (e) { if (e.target === overlay) close(false); });
    });
  };

})();
