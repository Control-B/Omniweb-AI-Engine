(function () {
  const state = { open: false };

  function getLauncher() {
    return document.querySelector('[data-presence-ai]');
  }

  function setOpen(open) {
    const launcher = getLauncher();
    state.open = open;
    if (launcher) {
      launcher.dataset.open = String(open);
      const button = launcher.querySelector('[data-presence-ai-toggle]');
      if (button) button.setAttribute('aria-expanded', String(open));
    }
  }

  window.PresenceAI = {
    open: function () {
      setOpen(true);
      document.dispatchEvent(new CustomEvent('presence-ai:open', { detail: getContext() }));
    },
    close: function () {
      setOpen(false);
      document.dispatchEvent(new CustomEvent('presence-ai:close'));
    },
    sendContext: function (extra) {
      const detail = Object.assign({}, getContext(), extra || {});
      document.dispatchEvent(new CustomEvent('presence-ai:context', { detail: detail }));
      return detail;
    }
  };

  function getContext() {
    const contextNode = document.querySelector('[data-presence-context]');
    let pageContext = {};
    if (contextNode) {
      try {
        pageContext = JSON.parse(contextNode.textContent || '{}');
      } catch (error) {
        pageContext = {};
      }
    }
    return Object.assign({}, window.PresenceAIContext || {}, pageContext);
  }

  document.addEventListener('click', function (event) {
    const toggle = event.target.closest('[data-presence-ai-toggle]');
    if (toggle) {
      setOpen(!state.open);
      if (state.open) window.PresenceAI.sendContext();
      return;
    }

    const close = event.target.closest('[data-presence-ai-close]');
    if (close) setOpen(false);

    const drawerOpen = event.target.closest('[data-cart-open]');
    if (drawerOpen) {
      const drawer = document.querySelector('[data-cart-drawer]');
      if (drawer) drawer.dataset.open = 'true';
    }

    const drawerClose = event.target.closest('[data-cart-close]');
    if (drawerClose) {
      const drawer = document.querySelector('[data-cart-drawer]');
      if (drawer) drawer.dataset.open = 'false';
    }

    const menuToggle = event.target.closest('[data-menu-toggle]');
    if (menuToggle) {
      const nav = document.querySelector('[data-site-nav]');
      const open = nav && nav.dataset.open !== 'true';
      if (nav) nav.dataset.open = String(open);
      menuToggle.setAttribute('aria-expanded', String(open));
    }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      setOpen(false);
      const drawer = document.querySelector('[data-cart-drawer]');
      if (drawer) drawer.dataset.open = 'false';
    }
  });

  document.addEventListener('DOMContentLoaded', function () {
    window.PresenceAI.sendContext();
  });
})();
