/*
 * "Modo demostración" del tótem dentro de index.html: abre el tótem, el panel de bodega o ambos a la vez.
 * Independiente del chatbot. Requiere totem/store.js (para reiniciar la demo).
 *
 * Botones: cualquier elemento con  data-tt-abrir="totem" | "bodega" | "ambas"
 */
(function () {
  'use strict';
  var BASE = (function () {
    // Carpeta de este script: funciona tanto en "/" como en un subdirectorio
    var s = document.currentScript;
    return s && s.src ? s.src.replace(/[^/]*$/, '') : 'totem/';
  })();
  var URL_TOTEM = BASE + 'totem.html?embed=1';
  var URL_BODEGA = BASE + 'bodega.html?embed=1';

  var modal = null, escena = null, ifTotem = null, ifBodega = null, abridor = null;

  function crear() {
    modal = document.createElement('div');
    modal.className = 'tt-modal';
    modal.hidden = true;
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-label', 'Modo demostración del tótem de autoatención');
    modal.innerHTML =
      '<div class="tt-barra">' +
      '<strong>Modo demostración · Tótem de autoatención</strong>' +
      '<div class="tt-modos" role="group" aria-label="Pantallas a mostrar">' +
      '<button type="button" data-modo="totem" aria-pressed="false">Tótem</button>' +
      '<button type="button" data-modo="bodega" aria-pressed="false">Panel de bodega</button>' +
      '<button type="button" data-modo="ambas" aria-pressed="false">Ambas pantallas</button></div>' +
      '<div class="tt-acc">' +
      '<a href="' + BASE + 'totem.html" target="_blank" rel="noopener">Abrir tótem en otra pestaña</a>' +
      '<a href="' + BASE + 'bodega.html" target="_blank" rel="noopener">Abrir bodega en otra pestaña</a>' +
      '<button type="button" data-reiniciar>Reiniciar demo</button>' +
      '<button type="button" class="tt-cerrar" data-cerrar>Cerrar ✕</button></div></div>' +
      '<div class="tt-escena" data-modo="ambas">' +
      '<div class="tt-equipo"><div class="tt-bisel"><iframe title="Tótem de autoatención (pantalla del cliente)"></iframe></div><span class="tt-etiqueta">Pantalla del cliente · tótem</span></div>' +
      '<div class="tt-estacion"><div class="tt-ventana"><iframe title="Panel de bodega (pantalla del trabajador)"></iframe></div><span class="tt-etiqueta">Pantalla del trabajador · bodega</span></div></div>';
    document.body.appendChild(modal);
    escena = modal.querySelector('.tt-escena');
    var ifs = modal.querySelectorAll('iframe');
    ifTotem = ifs[0]; ifBodega = ifs[1];
    // Esc también debe cerrar cuando el foco está dentro de un iframe (mismo origen)
    for (var k = 0; k < ifs.length; k++) ifs[k].addEventListener('load', function (ev) {
      try { ev.target.contentWindow.addEventListener('keydown', function (e) { if (e.key === 'Escape') cerrar(); }); } catch (x) { /* otro origen: se ignora */ }
    });

    modal.addEventListener('click', function (ev) {
      var m = ev.target.closest('[data-modo]');
      if (m && m.closest('.tt-modos')) { fijarModo(m.getAttribute('data-modo')); return; }
      if (ev.target.closest('[data-cerrar]')) cerrar();
      if (ev.target.closest('[data-reiniciar]')) reiniciar();
    });
  }

  function fijarModo(modo) {
    escena.setAttribute('data-modo', modo);
    var bs = modal.querySelectorAll('.tt-modos button');
    for (var i = 0; i < bs.length; i++) bs[i].setAttribute('aria-pressed', String(bs[i].getAttribute('data-modo') === modo));
  }

  function reiniciar() {
    if (window.PitsTotem && window.PitsTotem.Store) window.PitsTotem.Store.reiniciar();
    ifTotem.src = URL_TOTEM;   // vuelve a la pantalla de bienvenida
  }

  function abrir(modo) {
    if (!modal) crear();
    abridor = document.activeElement;
    // Los iframes se cargan la primera vez que se abre la demo
    if (!ifTotem.getAttribute('src')) { ifTotem.src = URL_TOTEM; ifBodega.src = URL_BODEGA; }
    fijarModo(modo === 'totem' || modo === 'bodega' ? modo : 'ambas');
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
    modal.querySelector('[data-cerrar]').focus();
  }

  function cerrar() {
    if (!modal) return;
    modal.hidden = true;
    document.body.style.overflow = '';
    if (abridor && abridor.focus) abridor.focus();
  }

  document.addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-tt-abrir]');
    if (b) abrir(b.getAttribute('data-tt-abrir'));
  });
  // Demo incrustada en la página: los iframes se cargan al mostrarse la opción 3
  function cargarIncrustada() {
    var ifs = document.querySelectorAll('#panel-totem iframe[data-tt-src]');
    for (var i = 0; i < ifs.length; i++) if (!ifs[i].getAttribute('src')) ifs[i].src = BASE + ifs[i].getAttribute('data-tt-src').replace(/^totem\//, '');
  }
  var panel = document.getElementById('panel-totem');
  if (panel) {
    if (window.MutationObserver) new MutationObserver(function () { if (!panel.hidden) cargarIncrustada(); }).observe(panel, { attributes: true, attributeFilter: ['hidden'] });
    if (!panel.hidden) cargarIncrustada();
  }
  document.addEventListener('click', function (ev) {
    if (ev.target.closest('[data-tt-reiniciar]')) {
      if (window.PitsTotem && window.PitsTotem.Store) window.PitsTotem.Store.reiniciar();
      var t = document.querySelector('#panel-totem iframe[data-tt-src*="totem.html"]');
      if (t) t.src = t.src;
    }
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && modal && !modal.hidden) cerrar();
  });

  window.TotemDemo = { abrir: abrir, cerrar: cerrar, reiniciar: reiniciar };
})();
