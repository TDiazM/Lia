/*
 * Estado compartido de pedidos entre el tótem y el panel de bodega.
 *
 * Funciona en dos modos:
 *  - CON SERVIDOR (página abierta desde FastAPI): los pedidos se guardan en el servidor (/api/pedidos),
 *    con número de pedido único, y todas las pantallas (incluso de otros equipos) se sincronizan por sondeo.
 *    Así quedan registrados en la plataforma (/plataforma).
 *  - SIN SERVIDOR (archivo abierto directo, o servidor caído): el estado vive en localStorage y cada cambio
 *    se avisa por BroadcastChannel y por el evento "storage", como en la demo original.
 * El localStorage sigue actuando como caché local en ambos modos.
 * No usa el chatbot.
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

  var API = '../api/pedidos';   // relativo: funciona en /totem, /bodega y /totem/*.html
  var SONDEO_MS = 2500;
  var epoca = 0;                // sube con cada escritura: descarta sondeos que quedaron viejos
  var enVuelo = 0;              // escrituras al servidor en curso

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

  /* ---------- servidor (opcional) ---------- */
  function hayServidor() { return !!(g.fetch && g.location && /^https?:$/.test(g.location.protocol)); }

  function pedir(metodo, url, cuerpo, ms) {
    return new Promise(function (resolve, reject) {
      var ctl = g.AbortController ? new g.AbortController() : null;
      var t = setTimeout(function () { if (ctl) ctl.abort(); reject(new Error('tiempo agotado')); }, ms || 3000);
      var op = { method: metodo, signal: ctl ? ctl.signal : undefined };
      if (cuerpo) { op.headers = { 'Content-Type': 'application/json' }; op.body = JSON.stringify(cuerpo); }
      g.fetch(url, op).then(function (r) {
        clearTimeout(t);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      }).then(resolve, function (e) { clearTimeout(t); reject(e); });
    });
  }

  function escritura(promesa) {          // marca una escritura al servidor como "en curso"
    epoca++; enVuelo++;
    var fin = function () { enVuelo--; epoca++; };
    promesa.then(fin, fin);
    return promesa;
  }

  function normalizar(p) {
    return { id: p.id, items: p.items, total: p.total, creado: p.creado, estado: p.estado, hist: p.hist || [] };
  }

  function firma(lista) { return JSON.stringify(lista.map(function (p) { return [p.id, p.estado]; })); }

  function sondear() {
    if (!hayServidor() || enVuelo > 0) return;
    var e0 = epoca;
    pedir('GET', API, null, 3000).then(function (r) {
      if (e0 !== epoca || enVuelo > 0) return;           // hubo un cambio mientras llegaba la respuesta
      var srv = (r.pedidos || []).map(normalizar), ids = {};
      srv.forEach(function (p) { ids[p.id] = true; });
      var d = leer();
      // los pedidos creados sin conexión se conservan (si no chocan con un número del servidor)
      var locales = d.pedidos.filter(function (p) { return p.local && !ids[p.id]; });
      var nuevo = srv.concat(locales);
      if (firma(nuevo) !== firma(d.pedidos)) { d.pedidos = nuevo; escribir(d); }
    }, function () { /* sin servidor: se sigue con el estado local */ });
  }

  function crearLocal(copia, total) {
    var d = leer();
    var ahora = new Date().toISOString();
    var pedido = { id: ++d.seq, items: copia, total: total, creado: ahora, estado: 0, hist: [{ estado: 0, ts: ahora }], local: true };
    d.pedidos.push(pedido);
    if (d.pedidos.length > MAX_PEDIDOS) d.pedidos.splice(0, d.pedidos.length - MAX_PEDIDOS);
    escribir(d);
    return pedido;
  }

  var Store = {
    ESTADOS: ESTADOS,
    listar: function () { return leer().pedidos.slice(); },
    obtener: function (id) {
      var p = leer().pedidos;
      for (var i = 0; i < p.length; i++) if (p[i].id === id) return p[i];
      return null;
    },
    // items: [{id, nombre, precio, cant}]. Devuelve una Promesa con el pedido (con servidor, el número lo asigna el servidor).
    crear: function (items) {
      var total = 0;
      var copia = items.map(function (it) {
        total += it.precio * it.cant;
        return { id: it.id, nombre: it.nombre, precio: it.precio, cant: it.cant };
      });
      if (!hayServidor()) return Promise.resolve(crearLocal(copia, total));
      return escritura(pedir('POST', API, { items: copia }, 4000)).then(function (p) {
        var d = leer(), n = normalizar(p);
        d.pedidos = d.pedidos.filter(function (x) { return x.id !== n.id; });
        d.pedidos.push(n);
        if (d.pedidos.length > MAX_PEDIDOS) d.pedidos.splice(0, d.pedidos.length - MAX_PEDIDOS);
        escribir(d);
        return n;
      }, function () { return crearLocal(copia, total); });   // servidor caído: se sigue en modo local
    },
    cambiarEstado: function (id, estado) {
      if (estado < 0 || estado > 3) return null;
      var d = leer();
      for (var i = 0; i < d.pedidos.length; i++) {
        if (d.pedidos[i].id === id && d.pedidos[i].estado !== estado) {
          d.pedidos[i].estado = estado;
          d.pedidos[i].hist.push({ estado: estado, ts: new Date().toISOString() });
          escribir(d);
          if (hayServidor() && !d.pedidos[i].local) {
            escritura(pedir('POST', API + '/' + id + '/estado', { estado: estado }, 3000)).then(null, function () { /* el sondeo corrige */ });
          }
          return d.pedidos[i];
        }
      }
      return Store.obtener(id);
    },
    // "Reiniciar demo": limpia el tablero; en el servidor los pedidos se archivan (siguen visibles en /plataforma)
    reiniciar: function () {
      escribir(vacio());
      if (hayServidor()) escritura(pedir('POST', API + '/reiniciar', null, 3000)).then(null, function () {});
    },
    suscribir: function (fn) {
      subs.push(fn);
      return function () { subs = subs.filter(function (s) { return s !== fn; }); };
    }
  };

  NS.Store = Store;

  if (hayServidor()) {
    setTimeout(sondear, 50);
    setInterval(sondear, SONDEO_MS);
    g.addEventListener('focus', sondear);
  }
})(window);
