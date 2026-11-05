/* HookedAZ archival controls; no network calls or data collection. */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root.document) {
    var ready = function () { api.initialize(root.document, root); };
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', ready);
    else ready();
  }
}(typeof window === 'undefined' ? {} : window, function () {
  'use strict';
  function initializeMenu(doc) {
    var panel = doc.getElementById('static-wrapper');
    if (!panel) return;
    var toggles = Array.prototype.slice.call(doc.querySelectorAll('#static-toggle, #menu-toggle'));
    var opener = null;
    function close(returnFocus) {
      panel.hidden = true; panel.inert = true; panel.classList.remove('active');
      toggles.forEach(function (button) { button.setAttribute('aria-expanded', 'false'); });
      if (returnFocus && opener) opener.focus();
    }
    close(false);
    // Capture prevents the old template's jQuery toggles from running a second time.
    doc.addEventListener('click', function (event) {
      var target = event.target.closest ? event.target : event.target.parentElement;
      if (!target) return;
      var toggle = target.closest('#static-toggle, #menu-toggle');
      var dismiss = target.closest('#static-close, #menu-close');
      if (toggle || dismiss) {
        event.preventDefault(); event.stopImmediatePropagation();
        if (dismiss || !panel.hidden) close(true);
        else {
          opener = toggle; panel.hidden = false; panel.inert = false; panel.classList.add('active');
          toggles.forEach(function (button) { button.setAttribute('aria-expanded', 'true'); });
        }
      } else if (!panel.hidden && panel.contains(target)) {
        var link = target.closest('a[href]');
        if (link) {
          event.stopImmediatePropagation(); close(false);
          var href = link.getAttribute('href');
          if (href && href.charAt(0) === '#' && href.length > 1) {
            var section = doc.getElementById(href.slice(1));
            if (section) { section.setAttribute('tabindex', '-1'); section.focus(); }
          }
        }
      }
    }, true);
    doc.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !panel.hidden) { event.preventDefault(); close(true); }
    });
  }
  function resizeFrame(frame) {
    try {
      if (frame.contentWindow && typeof frame.contentWindow.archiveResizeMap === 'function') frame.contentWindow.archiveResizeMap();
    } catch (_) { /* Only same-origin embedded maps participate. */ }
  }
  function initializeTabs(doc, win) {
    var tabs = Array.prototype.slice.call(doc.querySelectorAll('[role="tablist"] [role="tab"]'));
    function update(active) {
      tabs.forEach(function (tab) {
        var selected = tab === active;
        tab.setAttribute('aria-selected', selected ? 'true' : 'false'); tab.tabIndex = selected ? 0 : -1;
        var href = tab.getAttribute('href');
        var panel = href && doc.getElementById(href.slice(1));
        if (panel) {
          panel.setAttribute('aria-hidden', selected ? 'false' : 'true');
          if (selected) panel.querySelectorAll('iframe').forEach(function (frame) { resizeFrame(frame); });
        }
      });
    }
    if (!tabs.length) return;
    update(tabs.filter(function (t) { return t.parentElement.classList.contains('active'); })[0] || tabs[0]);
    if (win.jQuery) win.jQuery(tabs).on('shown.bs.tab', function () { update(this); });
    tabs.forEach(function (tab, index) {
      tab.addEventListener('keydown', function (event) {
        var next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null;
        if (next !== null) { event.preventDefault(); tabs[next].focus(); if (win.jQuery) win.jQuery(tabs[next]).tab('show'); }
      });
    });
    win.addEventListener('resize', function () { tabs.forEach(function (tab) { if (tab.getAttribute('aria-selected') === 'true') update(tab); }); });
  }
  function initialize(doc, win) {
    initializeMenu(doc); initializeTabs(doc, win);
    if (win.jQuery) {
      win.jQuery('#data-nav').on('shown.bs.collapse hidden.bs.collapse', function (event) {
        var expanded = event.type === 'shown';
        doc.querySelectorAll('[aria-controls="data-nav"]').forEach(function (button) { button.setAttribute('aria-expanded', expanded ? 'true' : 'false'); });
      });
    }
    var reduce = win.matchMedia && win.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduce) {
      var snow = doc.getElementById('snow');
      if (snow) { snow.pause(); snow.removeAttribute('autoplay'); }
    }
  }
  return { initialize: initialize, initializeMenu: initializeMenu, initializeTabs: initializeTabs, resizeFrame: resizeFrame };
}));
