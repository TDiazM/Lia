/*
 * Estado compartido de pedidos entre el tótem y el panel de bodega (simulación local).
 *
 * Los dos pueden estar en iframes, pestañas o ventanas del mismo navegador: el estado vive en
 * localStorage y cada cambio se avisa por BroadcastChannel y por el evento "storage".
 * Si el navegador bloquea localStorage, se usa memoria + BroadcastChannel.
 * No usa el backend ni el chatbot.
 */
(function (g) {
  'use strict';
  var NS = (g.PitsTotem = g.PitsTotem || {});

  var KEY = 'pits_totem_demo_v1';
  var CANAL = 'pits_totem_demo';
  var SEQ_INICIAL = 103;      // el primer pedido es el #104
  var MAX_PEDIDOS = 50;

  var ESTADOS = [
    { id: 0, bodega: 'Pedido recibido', cliente: 'Pedido recibido', paso: 'Recibido', accion: 'Comenzar preparación' },
    { id: 1, bodega: 'En preparación', cliente: 'Preparando pedido', paso: 'Preparando', accion: 'Marcar como listo' },
    { id: 2, bodega: 'Listo para retirar', cliente: '¡Listo para retirar!', paso: 'Listo', accion: 'Marcar como entregado' },
    { id: 3, bodega: 'Entregado', cliente: 'Entregado', paso: 'Entregado', accion: '' }
  ];

  var mem = null;
  var subs = [];
  var bc = null;
  try { bc = new BroadcastChannel(CANAL); } catch (e) { bc = null; }

  function vacio() { return { seq: SEQ_INICIAL, pedidos: [] }; }

  function valido(d) { return d && typeof d.seq === 'number' && Array.isArray(d.pedidos); }

  function leer() {
    try {
      var raw = g.localStorage.getItem(KEY);
      if (raw) {
        var d = JSON.parse(raw);
        if (valido(d)) { mem = d; return d; }
      }
    } catch (e) {}
    if (!mem) mem = vacio();
    return mem;
  }

  function avisar() {
    var d = leer();
    for (var i = 0; i < subs.length; i++) {
      try { subs[i](d); } catch (e) {}
    }
  }

  function escribir(d) {
    mem = d;
    try { g.localStorage.setItem(KEY, JSON.stringify(d)); } catch (e) {}
    if (bc) { try { bc.postMessage({ tipo: 'estado', data: d }); } catch (e) {} }
    avisar();
  }

  if (bc) {
    bc.onmessage = function (ev) {
      if (ev.data && ev.data.tipo === 'estado' && valido(ev.data.data)) { mem = ev.data.data; avisar(); }
    };
  }
  g.addEventListener('storage', function (ev) {
    if (ev.key === KEY || ev.key === null) {
      try { mem = ev.newValue ? JSON.parse(ev.newValue) : vacio(); } catch (e) { mem = vacio(); }
      avisar();
    }
  });

  var Store = {
    ESTADOS: ESTADOS,
    listar: function () { return leer().pedidos.slice(); },
    obtener: function (id) {
      var p = leer().pedidos;
      for (var i = 0; i < p.length; i++) if (p[i].id === id) return p[i];
      return null;
    },
    // items: [{id, nombre, precio, cant}]
    crear: function (items) {
      var d = leer();
      var ahora = new Date().toISOString();
      var total = 0;
      var copia = items.map(function (it) {
        total += it.precio * it.cant;
        return { id: it.id, nombre: it.nombre, precio: it.precio, cant: it.cant };
      });
      var pedido = { id: ++d.seq, items: copia, total: total, creado: ahora, estado: 0, hist: [{ estado: 0, ts: ahora }] };
      d.pedidos.push(pedido);
      if (d.pedidos.length > MAX_PEDIDOS) d.pedidos.splice(0, d.pedidos.length - MAX_PEDIDOS);
      escribir(d);
      return pedido;
    },
    cambiarEstado: function (id, estado) {
      if (estado < 0 || estado > 3) return null;
      var d = leer();
      for (var i = 0; i < d.pedidos.length; i++) {
        if (d.pedidos[i].id === id && d.pedidos[i].estado !== estado) {
          d.pedidos[i].estado = estado;
          d.pedidos[i].hist.push({ estado: estado, ts: new Date().toISOString() });
          escribir(d);
          return d.pedidos[i];
        }
      }
      return Store.obtener(id);
    },
    reiniciar: function () { escribir(vacio()); },
    suscribir: function (fn) {
      subs.push(fn);
      return function () { subs = subs.filter(function (s) { return s !== fn; }); };
    }
  };

  NS.Store = Store;
})(window);
