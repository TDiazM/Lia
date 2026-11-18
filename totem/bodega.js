/*
 * Panel de bodega: muestra los pedidos del tótem y permite cambiar su estado.
 * Independiente del chatbot. Comparte pedidos con el tótem mediante PitsTotem.Store.
 */
(function () {
  'use strict';
  var T = window.PitsTotem, C = T.Catalogo, Store = T.Store, ES = Store.ESTADOS;
  var vistos = null;   // ids ya dibujados, para resaltar solo los pedidos nuevos
  var nuevos = {};

  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  function tarjeta(p) {
    var unidades = p.items.reduce(function (a, i) { return a + i.cant; }, 0);
    var botones = ES.map(function (s) {
      return '<button type="button" data-pedido="' + p.id + '" data-estado="' + s.id + '" aria-pressed="' + (p.estado === s.id) + '" title="' + esc(s.bodega) + '">' + (s.id + 1) + '</button>';
    }).join('');
    var accion = p.estado < 3
      ? '<button type="button" class="avanzar' + (p.estado === 1 ? ' ok' : '') + '" data-pedido="' + p.id + '" data-estado="' + (p.estado + 1) + '">' + esc(ES[p.estado].accion) + '</button>'
      : '<div class="estado-final">✓ Pedido entregado</div>';
    return '<article class="pedido e' + p.estado + (nuevos[p.id] ? ' nuevo' : '') + '" aria-label="Pedido ' + p.id + ': ' + esc(ES[p.estado].bodega) + '">' +
      '<header><strong>#' + p.id + '</strong><time datetime="' + esc(p.creado) + '">Recibido ' + C.fmtHora(p.creado, true) + '</time></header>' +
      '<ul class="lineas">' + p.items.map(function (i) { return '<li><b>' + i.cant + '×</b><span>' + esc(i.nombre) + '</span></li>'; }).join('') + '</ul>' +
      '<div class="total">' + unidades + (unidades === 1 ? ' unidad' : ' unidades') + ' · ' + C.fmtCLP(p.total) + '</div>' +
      '<div class="estados" role="group" aria-label="Cambiar estado del pedido ' + p.id + '">' + botones + '</div>' + accion + '</article>';
  }

  function render(datos) {
    var pedidos = Store.listar();
    if (vistos === null) { vistos = {}; pedidos.forEach(function (p) { vistos[p.id] = true; }); }
    Object.keys(vistos).forEach(function (id) {
      if (!pedidos.some(function (p) { return String(p.id) === id; })) delete vistos[id];
    });
    pedidos.forEach(function (p) {
      if (!vistos[p.id]) {
        vistos[p.id] = true; nuevos[p.id] = true;
        (function (id) { setTimeout(function () { delete nuevos[id]; }, 2600); })(p.id);
        document.title = '🔔 Nuevo pedido #' + p.id + ' | Panel de bodega';
      }
    });
    var cuenta = [0, 0, 0, 0];
    var cols = ES.map(function (s) {
      var lista = pedidos.filter(function (p) { return p.estado === s.id; });
      cuenta[s.id] = lista.length;
      return '<section class="col c' + s.id + '" aria-label="' + esc(s.bodega) + '">' +
        '<div class="col-cab">' + esc(s.bodega) + '<span>' + lista.length + '</span></div>' +
        '<div class="col-cuerpo">' + (lista.length ? lista.map(tarjeta).join('') : '<div class="col-vacia">Sin pedidos</div>') + '</div></section>';
    }).join('');
    document.getElementById('tablero').innerHTML = (pedidos.length ? '' : '<p class="espera">Esperando pedidos del tótem…</p>') + cols;
    document.getElementById('contadores').innerHTML =
      '<div class="cont"><b>' + cuenta[0] + '</b>Nuevos</div><div class="cont"><b>' + cuenta[1] + '</b>En preparación</div><div class="cont"><b>' + cuenta[2] + '</b>Listos</div>';
    void datos;
  }

  document.addEventListener('click', function (ev) {
    var b = ev.target.closest('button[data-pedido]');
    if (b) { Store.cambiarEstado(parseInt(b.getAttribute('data-pedido'), 10), parseInt(b.getAttribute('data-estado'), 10)); return; }
    if (ev.target.closest('#btn-reinicio')) { vistos = {}; nuevos = {}; document.title = 'Panel de bodega | Demo'; Store.reiniciar(); }
  });
  window.addEventListener('focus', function () { document.title = 'Panel de bodega | Demo'; });

  Store.suscribir(render);
  render();
})();
