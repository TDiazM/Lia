/*
 * Asistente de cotizaciones - widget incrustable.
 *
 * Uso (pegar antes de </body>):
 *   <script src="https://TU-SERVIDOR/widget.js" defer></script>
 *
 * Atributos opcionales en la etiqueta <script>:
 *   data-api="https://TU-SERVIDOR"   (por defecto, el mismo origen que widget.js)
 *   data-titulo="Asistente Pits"     (título del encabezado)
 *   data-color="#283627"             (color principal, formato hexadecimal)
 *
 * Todo vive dentro de un Shadow DOM: no hereda ni rompe los estilos del sitio donde se incrusta.
 * API pública:  window.PitsChat.open(), window.PitsChat.send("texto")
 */
(function () {
  'use strict';
  if (window.PitsChat) return;

  var script = document.currentScript;
  var ds = (script && script.dataset) || {};

  function origenDeScript() {
    try {
      if (script && script.src) return new URL(script.src, location.href).origin;
    } catch (e) {}
    return '';
  }
  var API = (ds.api || origenDeScript() || (location.protocol === 'file:' ? 'http://localhost:8000' : '')).replace(/\/$/, '');
  var TITULO = (ds.titulo || 'Asistente de cotizaciones').slice(0, 40);
  var COLOR = /^#[0-9a-f]{3,8}$/i.test(ds.color || '') ? ds.color : '#283627';
  var ACENTO = '#C9796A';

  var sessionId = null;
  try { sessionId = sessionStorage.getItem('pits_widget_session'); } catch (e) {}
  if (!sessionId) {
    sessionId = 'w_' + Math.random().toString(36).slice(2, 12);
    try { sessionStorage.setItem('pits_widget_session', sessionId); } catch (e) {}
  }

  var CSS = [
    ':host{all:initial}',
    '*{box-sizing:border-box;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}',
    '.burbuja{position:fixed;right:20px;bottom:20px;z-index:2147483000;width:60px;height:60px;border-radius:50%;border:0;cursor:pointer;background:' + COLOR + ';color:#fff;font-size:26px;box-shadow:0 6px 20px rgba(0,0,0,.28);display:flex;align-items:center;justify-content:center}',
    '.burbuja:hover{transform:scale(1.05)}',
    '.burbuja:focus-visible,.cerrar:focus-visible,.enviar:focus-visible,.chip:focus-visible,.mas:focus-visible,input:focus-visible{outline:3px solid ' + ACENTO + ';outline-offset:2px}',
    '.panel{position:fixed;right:20px;bottom:92px;z-index:2147483000;width:min(380px,calc(100vw - 24px));height:min(560px,calc(100vh - 116px));background:#fff;border-radius:16px;box-shadow:0 12px 40px rgba(0,0,0,.3);display:none;flex-direction:column;overflow:hidden;border:1px solid #e5e0cf}',
    '.panel.abierto{display:flex}',
    '.cab{background:' + COLOR + ';color:#fff;padding:12px 14px;display:flex;align-items:center;justify-content:space-between;gap:8px}',
    '.cab strong{font-size:15px}',
    '.estado{font-size:11px;opacity:.85;display:block;margin-top:2px}',
    '.cerrar{background:transparent;border:0;color:#fff;font-size:22px;cursor:pointer;line-height:1;padding:4px 8px;border-radius:8px}',
    '.msgs{flex:1;overflow-y:auto;padding:12px;background:#faf7ee;display:flex;flex-direction:column;gap:8px}',
    '.m{max-width:88%;padding:9px 12px;border-radius:14px;font-size:13.5px;line-height:1.45;word-wrap:break-word;overflow-wrap:anywhere}',
    '.bot{background:#fff;color:#1f2a1e;border:1px solid #ebdcb4;border-top-left-radius:4px;align-self:flex-start}',
    '.user{background:' + COLOR + ';color:#fff;border-top-right-radius:4px;align-self:flex-end}',
    '.fila{display:flex;gap:8px;align-items:flex-start;margin:5px 0}',
    '.mas{flex:none;background:' + ACENTO + ';color:#fff;border:0;border-radius:8px;padding:4px 9px;font-size:12px;font-weight:600;cursor:pointer}',
    '.mas:hover{filter:brightness(.92)}',
    '.pdf{display:inline-block;margin-top:8px;background:' + ACENTO + ';color:#fff;text-decoration:none;padding:7px 12px;border-radius:8px;font-weight:600;font-size:13px}',
    '.chips{display:flex;flex-wrap:wrap;gap:6px;padding:8px 12px 0;background:#faf7ee}',
    '.chip{border:1px solid #cde2c7;background:#fff;color:#283627;border-radius:999px;padding:4px 10px;font-size:12px;cursor:pointer}',
    '.chip.fuerte{background:' + ACENTO + ';border-color:' + ACENTO + ';color:#fff;font-weight:600}',
    '.form{display:flex;gap:8px;padding:10px 12px;background:#faf7ee;border-top:1px solid #ebdcb4}',
    '.form input{flex:1;border:1px solid #cdbf93;border-radius:10px;padding:9px 11px;font-size:14px;background:#fff;color:#1f2a1e;min-width:0}',
    '.enviar{border:0;background:' + COLOR + ';color:#fff;border-radius:10px;padding:0 14px;font-size:14px;font-weight:600;cursor:pointer}',
    '.enviar:disabled{opacity:.5;cursor:default}',
    '@media (prefers-reduced-motion:no-preference){.burbuja{transition:transform .15s}}'
  ].join('');

  var host = document.createElement('div');
  host.setAttribute('data-pits-chat', '');
  var root = host.attachShadow({ mode: 'open' });

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  var style = document.createElement('style');
  style.textContent = CSS;

  var burbuja = el('button', 'burbuja', '💬');
  burbuja.type = 'button';
  burbuja.setAttribute('aria-label', 'Abrir asistente de cotizaciones');
  burbuja.setAttribute('aria-expanded', 'false');

  var panel = el('div', 'panel');
  panel.setAttribute('role', 'dialog');
  panel.setAttribute('aria-label', TITULO);

  var cab = el('div', 'cab');
  var tit = el('div');
  tit.appendChild(el('strong', null, TITULO));
  var estado = el('span', 'estado', 'Conectando…');
  tit.appendChild(estado);
  var cerrar = el('button', 'cerrar', '×');
  cerrar.type = 'button';
  cerrar.setAttribute('aria-label', 'Cerrar asistente');
  cab.appendChild(tit);
  cab.appendChild(cerrar);

  var msgs = el('div', 'msgs');
  msgs.setAttribute('role', 'log');
  msgs.setAttribute('aria-live', 'polite');

  var chips = el('div', 'chips');
  [['shampoo', false], ['cera', false], ['microfibra', false], ['carrito', false], ['📄 Cotizar (PDF)', true]].forEach(function (c) {
    var b = el('button', 'chip' + (c[1] ? ' fuerte' : ''), c[0]);
    b.type = 'button';
    b.addEventListener('click', function () { enviar(c[1] ? 'cotizar' : c[0]); });
    chips.appendChild(b);
  });

  var form = el('form', 'form');
  var input = el('input');
  input.type = 'text';
  input.maxLength = 200;
  input.placeholder = 'Escribe un producto…';
  input.setAttribute('aria-label', 'Mensaje');
  input.autocomplete = 'off';
  var btn = el('button', 'enviar', 'Enviar');
  btn.type = 'submit';
  form.appendChild(input);
  form.appendChild(btn);

  panel.appendChild(cab);
  panel.appendChild(msgs);
  panel.appendChild(chips);
  panel.appendChild(form);
  root.appendChild(style);
  root.appendChild(burbuja);
  root.appendChild(panel);

  function bajar() { msgs.scrollTop = msgs.scrollHeight; }

  function burbujaUsuario(texto) {
    msgs.appendChild(el('div', 'm user', texto));
    bajar();
  }

  // Convierte la respuesta del servidor en nodos DOM (sin innerHTML: el texto nunca se interpreta como HTML)
  function burbujaBot(texto, pdfUrl) {
    var m = el('div', 'm bot');
    String(texto).split('\n').forEach(function (linea, i) {
      var op = linea.match(/^\[(\d+)\]\s*(.*)$/);
      if (op) {
        var fila = el('div', 'fila');
        var mas = el('button', 'mas', '+ ' + op[1]);
        mas.type = 'button';
        mas.setAttribute('aria-label', 'Agregar opción ' + op[1] + ' al carrito');
        mas.addEventListener('click', function () { enviar(op[1]); });
        fila.appendChild(mas);
        fila.appendChild(el('span', null, op[2]));
        m.appendChild(fila);
      } else {
        if (i > 0 && m.lastChild && m.lastChild.className !== 'fila') m.appendChild(document.createElement('br'));
        m.appendChild(document.createTextNode(linea));
      }
    });
    if (pdfUrl) {
      m.appendChild(document.createElement('br'));
      var a = el('a', 'pdf', '📄 Descargar cotización PDF');
      a.href = API + pdfUrl;
      a.target = '_blank';
      a.rel = 'noopener';
      m.appendChild(a);
    }
    msgs.appendChild(m);
    bajar();
    return m;
  }

  function setEstado(texto) { estado.textContent = texto; }

  var enviando = false;
  function enviar(texto) {
    texto = String(texto || '').trim();
    if (!texto || enviando) return Promise.resolve();
    enviando = true;
    btn.disabled = true;
    abrir();
    burbujaUsuario(texto);
    var espera = burbujaBot('Escribiendo…');
    return fetch(API + '/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mensaje: texto, session_id: sessionId })
    })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) {
        espera.remove();
        burbujaBot(d.respuesta, d.pdf);
        setEstado('En línea');
      })
      .catch(function () {
        espera.remove();
        burbujaBot('No pude conectar con el asistente. Intenta de nuevo en unos minutos.');
        setEstado('Sin conexión');
      })
      .then(function () { enviando = false; btn.disabled = false; });
  }

  var saludado = false;
  function abrir() {
    panel.classList.add('abierto');
    burbuja.setAttribute('aria-expanded', 'true');
    if (!saludado) {
      saludado = true;
      burbujaBot('👋 ¡Hola! Dime qué producto buscas (ej: shampoo, cera, microfibra). Luego agrega opciones al carrito y pide tu cotización en PDF.');
      // El chequeo inicial solo informa mientras el estado siga en 'Conectando…' (un chat fallido o exitoso manda)
      var soloSiPendiente = function (t) { if (estado.textContent === 'Conectando…') setEstado(t); };
      fetch(API + '/api/health').then(function (r) { soloSiPendiente(r.ok ? 'En línea' : 'Sin conexión'); }).catch(function () { soloSiPendiente('Sin conexión'); });
    }
    setTimeout(function () { input.focus(); }, 0);
  }
  function cerrarPanel() {
    panel.classList.remove('abierto');
    burbuja.setAttribute('aria-expanded', 'false');
    burbuja.focus();
  }

  burbuja.addEventListener('click', function () { panel.classList.contains('abierto') ? cerrarPanel() : abrir(); });
  cerrar.addEventListener('click', cerrarPanel);
  panel.addEventListener('keydown', function (e) { if (e.key === 'Escape') cerrarPanel(); });
  form.addEventListener('submit', function (e) {
    e.preventDefault();
    var t = input.value;
    input.value = '';
    enviar(t);
  });

  window.PitsChat = { open: abrir, close: cerrarPanel, send: enviar };

  function montar() { document.body.appendChild(host); }
  if (document.body) montar(); else document.addEventListener('DOMContentLoaded', montar);
})();
