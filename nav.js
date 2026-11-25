/*
 * Barra de navegación compartida del ecosistema PITS (Shadow DOM: no hereda ni pisa estilos de la página).
 *
 * Se incluye en las páginas de demostración:  <script src="/nav.js" defer></script>
 * Muestra: "Volver al inicio" + menú para saltar entre Chatbot Web, Tótem, Panel de bodega y WhatsApp.
 * No se muestra dentro de un iframe ni con ?embed=1 (p. ej. la demo incrustada en la landing).
 *
 * Reserva su alto en la variable CSS --pits-nav-h (44px) para que cada página la use como margen superior.
 */
(function () {
  'use strict';
  if (window.__pitsNav) return;
  try { if (window.top !== window.self) return; } catch (e) { return; }
  if (/[?&]embed=1(&|$)/.test(location.search)) return;
  window.__pitsNav = true;

  var ALTO = 44;
  var ITEMS = [
    { id: 'inicio',   texto: 'Inicio',                href: '/' },
    { id: 'chatbot',  texto: 'Chatbot Web',           href: '/chatbot' },
    { id: 'totem',    texto: 'Tótem de Autoatención', href: '/totem' },
    { id: 'bodega',   texto: 'Panel de bodega',       href: '/bodega', nuevaPestana: true, sub: true },
    { id: 'plataforma', texto: 'Plataforma',         href: '/plataforma' },
    { id: 'whatsapp', texto: 'WhatsApp',              href: '/whatsapp', etiqueta: 'Próximamente' }
  ];

  function actual() {
    var p = location.pathname.replace(/\/+$/, '') || '/';
    if (p === '/') return 'inicio';
    if (p === '/chatbot' || p === '/demo') return 'chatbot';
    if (p === '/totem' || p === '/totem/totem.html') return 'totem';
    if (p === '/bodega' || p === '/totem/bodega.html') return 'bodega';
    if (p === '/whatsapp') return 'whatsapp';
    if (p === '/plataforma' || p === '/login' || p === '/admin' || p === '/cliente') return 'plataforma';
    return '';
  }

  var CSS =
    ':host{all:initial;position:fixed;top:0;left:0;right:0;height:' + ALTO + 'px;z-index:2147483000;display:block;' +
    'font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:13px;line-height:1}' +
    '*{box-sizing:border-box}' +
    '.barra{height:100%;display:flex;align-items:center;gap:10px;padding:0 12px;background:#283627;color:#faf7ee;' +
    'border-bottom:1px solid rgba(205,226,199,.25);box-shadow:0 2px 10px rgba(0,0,0,.18)}' +
    'a,button{font:inherit;color:inherit;text-decoration:none;cursor:pointer;border:0;background:none}' +
    'a:focus-visible,button:focus-visible{outline:2px solid #c9796a;outline-offset:2px}' +
    '.volver{display:inline-flex;align-items:center;gap:6px;background:#c9796a;color:#fff;font-weight:700;padding:8px 12px;' +
    'border-radius:10px;white-space:nowrap;transition:background .2s,transform .15s}' +
    '.volver:hover{background:#b56354}.volver:active{transform:scale(.97)}' +
    '.marca{font-weight:800;letter-spacing:.14em;font-size:11px;color:#cde2c7;white-space:nowrap}' +
    '.sep{width:1px;height:20px;background:rgba(205,226,199,.3)}' +
    '.enlaces{display:flex;align-items:center;gap:4px;margin-left:auto;overflow:hidden}' +
    '.enlaces a{display:inline-flex;align-items:center;gap:6px;padding:8px 11px;border-radius:9px;color:#cde2c7;white-space:nowrap;transition:background .2s,color .2s}' +
    '.enlaces a:hover{background:rgba(250,247,238,.12);color:#faf7ee}' +
    '.enlaces a[aria-current="page"]{background:#f6efd9;color:#283627;font-weight:700}' +
    '.enlaces a.sub{font-size:12px;opacity:.9}' +
    '.tag{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;padding:2px 6px;border-radius:99px;background:rgba(201,121,106,.28);color:#f6d6cf}' +
    '[aria-current="page"] .tag{background:rgba(201,121,106,.25);color:#8a4a3d}' +
    '.burger{display:none;margin-left:auto;padding:8px 11px;border-radius:9px;border:1px solid rgba(205,226,199,.35);color:#faf7ee;font-weight:600}' +
    '.burger:hover{background:rgba(250,247,238,.12)}' +
    '@media (max-width:820px){.enlaces{display:none}.burger{display:inline-flex;align-items:center;gap:6px}.marca,.sep{display:none}' +
    '.enlaces.abierto{display:flex;position:fixed;top:' + ALTO + 'px;left:8px;right:8px;margin:0;flex-direction:column;align-items:stretch;gap:2px;' +
    'background:#283627;border:1px solid rgba(205,226,199,.25);border-radius:12px;padding:8px;box-shadow:0 14px 30px rgba(0,0,0,.35);overflow:visible;animation:ent .18s ease}' +
    '.enlaces.abierto a{padding:13px 12px;font-size:14px}}' +
    '@keyframes ent{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}' +
    '@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}' +
    '@media print{:host{display:none!important}}';

  function montar() {
    var host = document.createElement('div');
    host.id = 'pits-nav';
    var sh = host.attachShadow({ mode: 'open' });
    var cur = actual();
    var enlaces = ITEMS.map(function (it) {
      return '<a href="' + it.href + '"' + (it.id === cur ? ' aria-current="page"' : '') +
        (it.nuevaPestana ? ' target="_blank" rel="noopener"' : '') + (it.sub ? ' class="sub"' : '') + '>' +
        it.texto + (it.etiqueta ? ' <span class="tag">' + it.etiqueta + '</span>' : '') + (it.nuevaPestana ? ' ↗' : '') + '</a>';
    }).join('');
    sh.innerHTML =
      '<style>' + CSS + '</style>' +
      '<nav class="barra" aria-label="Navegación PITS">' +
      '<a class="volver" href="/" title="Volver a la página principal"><span aria-hidden="true">←</span> Volver al inicio</a>' +
      '<span class="sep"></span><span class="marca">PITS · DEMOS</span>' +
      '<div class="enlaces" id="enl">' + enlaces + '</div>' +
      '<button type="button" class="burger" id="bur" aria-expanded="false" aria-controls="enl"><span aria-hidden="true">☰</span> Menú</button>' +
      '</nav>';
    document.body.appendChild(host);
    document.documentElement.style.setProperty('--pits-nav-h', ALTO + 'px');

    var enl = sh.getElementById('enl'), bur = sh.getElementById('bur');
    function cerrar() { enl.classList.remove('abierto'); bur.setAttribute('aria-expanded', 'false'); }
    bur.addEventListener('click', function (e) {
      e.stopPropagation();
      var ab = enl.classList.toggle('abierto');
      bur.setAttribute('aria-expanded', String(ab));
    });
    sh.addEventListener('click', function (e) { if (e.target.closest && e.target.closest('.enlaces a')) cerrar(); });
    document.addEventListener('click', cerrar);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') cerrar(); });
  }

  if (document.body) montar(); else document.addEventListener('DOMContentLoaded', montar);
})();
