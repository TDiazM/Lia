/*
 * Lógica del tótem de autoatención: pantallas, carrito, pedido y ticket.
 * Independiente del chatbot. Usa PitsTotem.Catalogo (datos) y PitsTotem.Store (pedidos compartidos con bodega).
 */
(function () {
  'use strict';
  var T = window.PitsTotem;
  var C = T.Catalogo, Store = T.Store;
  var MAX_CANT = 20;

  var st = {
    vista: 'bienvenida',
    cat: C.CATEGORIAS[0].id,
    carrito: {},          // id de producto -> cantidad
    pedidoId: null,
    estadoVisto: null     // último estado mostrado del pedido (para detectar el paso a "Listo")
  };

  function $(s) { return document.querySelector(s); }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }

  /* ---------- carrito ---------- */
  function lineas() {
    var out = [];
    C.PRODUCTOS.forEach(function (p) {
      var n = st.carrito[p.id];
      if (n > 0) out.push({ p: p, cant: n });
    });
    return out;
  }
  function totales() {
    var cant = 0, total = 0;
    lineas().forEach(function (l) { cant += l.cant; total += l.cant * l.p.precio; });
    return { cant: cant, total: total };
  }
  function cambiar(id, delta) {
    var n = (st.carrito[id] || 0) + delta;
    if (n > MAX_CANT) { aviso('Máximo ' + MAX_CANT + ' unidades por producto'); n = MAX_CANT; }
    if (n <= 0) delete st.carrito[id]; else st.carrito[id] = n;
    if (st.vista === 'catalogo') { actualizarAccion(id); actualizarBarra(); }
    else if (st.vista === 'carrito') renderCarrito();
    var cab = $('.cab-carrito');
    if (cab && delta > 0) { cab.classList.remove('rebota'); void cab.offsetWidth; cab.classList.add('rebota'); }
    actualizarCuenta();
  }

  /* ---------- navegación ---------- */
  function ir(nombre) {
    st.vista = nombre;
    var vistas = document.querySelectorAll('.vista');
    for (var i = 0; i < vistas.length; i++) vistas[i].classList.remove('activa');
    $('#v-' + nombre).classList.add('activa');
    if (nombre === 'catalogo') { renderTabs(); renderLista(); actualizarBarra(); actualizarCuenta(); }
    if (nombre === 'carrito') renderCarrito();
    if (nombre === 'resumen') renderResumen();
    if (nombre === 'seguimiento') renderSeguimiento();
    if (nombre === 'ticket') renderTicket();
  }

  /* ---------- catálogo ---------- */
  function renderTabs() {
    $('#tabs').innerHTML = C.CATEGORIAS.map(function (c) {
      return '<button type="button" role="tab" class="tab" data-acc="cat" data-cat="' + c.id + '" aria-selected="' + (c.id === st.cat) + '">' +
        '<span aria-hidden="true">' + c.icono + '</span>' + esc(c.corto) + '</button>';
    }).join('');
  }
  function accionHTML(p) {
    var n = st.carrito[p.id] || 0;
    if (!n) return '<button type="button" class="btn btn-agregar" data-acc="mas" data-id="' + p.id + '" aria-label="Agregar ' + esc(p.nombre) + ' al carrito">+ Agregar</button>';
    return '<div class="stepper"><button type="button" data-acc="menos" data-id="' + p.id + '" aria-label="Quitar una unidad">−</button>' +
      '<output aria-label="Cantidad">' + n + '</output>' +
      '<button type="button" data-acc="mas" data-id="' + p.id + '" aria-label="Agregar una unidad">+</button></div>';
  }
  function renderLista() {
    var cat = C.CATEGORIAS.filter(function (c) { return c.id === st.cat; })[0];
    var html = '<h3 class="cat-titulo">' + esc(cat.nombre) + '</h3><div class="grid">' +
      C.PRODUCTOS.filter(function (p) { return p.cat === st.cat; }).map(function (p) {
        return '<article class="tarjeta" data-prod="' + p.id + '">' +
          '<div class="foto">' + C.imagenSVG(p) + '</div>' +
          '<h3>' + esc(p.nombre) + '</h3><p class="desc">' + esc(p.desc) + '</p>' +
          '<span class="precio">' + C.fmtCLP(p.precio) + '</span>' +
          '<div class="acc" data-acc-de="' + p.id + '">' + accionHTML(p) + '</div></article>';
      }).join('') + '</div>';
    var lista = $('#lista');
    lista.innerHTML = html;
    lista.scrollTop = 0;
  }
  function actualizarAccion(id) {
    var p = C.porId(id), cont = document.querySelector('[data-acc-de="' + id + '"]');
    if (p && cont) cont.innerHTML = accionHTML(p);
  }
  function actualizarBarra() {
    var t = totales(), b = $('#barra-carrito');
    if (!t.cant) { b.disabled = true; b.textContent = 'Tu carrito está vacío'; return; }
    b.disabled = false;
    b.innerHTML = '<span aria-hidden="true">🛒</span> Ver carrito · <b>' + t.cant + (t.cant === 1 ? ' producto' : ' productos') + '</b> · <b>' + C.fmtCLP(t.total) + '</b>';
  }
  function actualizarCuenta() { $('#cab-cuenta').textContent = totales().cant; }

  /* ---------- carrito ---------- */
  function renderCarrito() {
    var ls = lineas(), cont = $('#items-carrito');
    if (!ls.length) {
      cont.innerHTML = '<div class="vacio"><span aria-hidden="true">🛒</span>Tu carrito está vacío.<br>Vuelve al catálogo para agregar productos.</div>';
    } else {
      cont.innerHTML = ls.map(function (l) {
        var p = l.p;
        return '<div class="item"><div class="foto">' + C.imagenSVG(p) + '</div>' +
          '<div class="info"><b>' + esc(p.nombre) + '</b><small>' + C.fmtCLP(p.precio) + ' c/u</small></div>' +
          '<button type="button" class="quitar" data-acc="quitar" data-id="' + p.id + '" aria-label="Eliminar ' + esc(p.nombre) + '">🗑</button>' +
          '<div class="cant"><div class="stepper"><button type="button" data-acc="menos" data-id="' + p.id + '"' + (l.cant <= 1 ? ' disabled' : '') + ' aria-label="Quitar una unidad">−</button>' +
          '<output aria-label="Cantidad">' + l.cant + '</output>' +
          '<button type="button" data-acc="mas" data-id="' + p.id + '" aria-label="Agregar una unidad">+</button></div></div>' +
          '<div class="sub">' + C.fmtCLP(l.cant * p.precio) + '</div></div>';
      }).join('');
    }
    $('#carrito-total').textContent = C.fmtCLP(totales().total);
    $('#btn-confirmar').disabled = !ls.length;
  }

  /* ---------- resumen ---------- */
  function renderResumen() {
    var ls = lineas();
    $('#tabla-resumen').innerHTML = '<div class="fila cab-t"><span>Producto</span><span class="num">Cant.</span><span class="num">P. unit.</span><span class="num">Subtotal</span></div>' +
      ls.map(function (l) {
        return '<div class="fila"><span>' + esc(l.p.nombre) + '</span><span class="num">' + l.cant + '</span><span class="num">' + C.fmtCLP(l.p.precio) + '</span><span class="num"><b>' + C.fmtCLP(l.cant * l.p.precio) + '</b></span></div>';
      }).join('');
    $('#resumen-total').textContent = C.fmtCLP(totales().total);
  }
  function enviarPedido() {
    var ls = lineas();
    if (!ls.length) return;
    var pedido = Store.crear(ls.map(function (l) { return { id: l.p.id, nombre: l.p.nombre, precio: l.p.precio, cant: l.cant }; }));
    st.pedidoId = pedido.id;
    st.estadoVisto = pedido.estado;
    st.carrito = {};
    ir('seguimiento');
  }

  /* ---------- seguimiento ---------- */
  var MENSAJES = [
    'Tu pedido llegó a bodega y está en la cola de preparación.',
    'Nuestro equipo está reuniendo tus productos.',
    '¡Tu pedido está listo para retirar! Acércate al mesón con tu número.',
    '¡Gracias por tu compra! Que disfrutes tus productos.'
  ];
  function renderSeguimiento() {
    var p = Store.obtener(st.pedidoId);
    if (!p) { return; }
    var e = p.estado, ES = Store.ESTADOS;
    var pasos = ES.map(function (s, i) {
      var cls = i < e ? 'hecho' : (i === e ? 'actual' : '');
      return '<div class="paso ' + cls + '"><b>' + (i < e || (i === e && e === 3) ? '✓' : (i + 1)) + '</b>' + esc(s.paso) + '</div>';
    }).join('');
    var relleno = e === 0 ? 0 : (e / 3) * 75;
    var cuerpo;
    if (e === 2) cuerpo = '<div class="aviso listo" role="alert">¡Tu pedido está listo para retirar!</div>';
    else if (e === 3) cuerpo = '<div class="aviso">' + MENSAJES[3] + '</div>';
    else cuerpo = '<div class="aviso">' + MENSAJES[e] + '<div class="barra" aria-hidden="true"></div></div>';

    $('#seg-contenido').innerHTML =
      '<div class="check" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg></div>' +
      '<h2 id="t-seg">¡Pedido enviado correctamente!</h2>' +
      '<div class="seg-num"><small>Número de pedido</small><b>#' + p.id + '</b></div>' +
      '<div class="estado-chip e' + e + '"><i></i><span>' + esc(ES[e].cliente) + '</span></div>' +
      '<div class="pasos" role="img" aria-label="Progreso: ' + esc(ES[e].bodega) + '"><div class="relleno" style="width:' + relleno + '%"></div>' + pasos + '</div>' +
      cuerpo +
      '<div class="acciones"><button type="button" class="btn btn-prim" data-acc="ver-ticket">Ver mi ticket</button>' +
      '<button type="button" class="btn btn-sec" data-acc="finalizar">Finalizar y volver al inicio</button></div>';
  }

  function chime() {
    try {
      var AC = window.AudioContext || window.webkitAudioContext, ac = new AC();
      [880, 1175].forEach(function (f, i) {
        var o = ac.createOscillator(), g = ac.createGain(), t = ac.currentTime + i * 0.18;
        o.frequency.value = f; o.connect(g); g.connect(ac.destination);
        g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.2, t + 0.02); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.4);
        o.start(t); o.stop(t + 0.45);
      });
    } catch (e) {}
  }

  /* ---------- ticket ---------- */
  function renderTicket() {
    var p = Store.obtener(st.pedidoId);
    if (!p) return;
    var filas = p.items.map(function (it) {
      return '<tr><td>' + esc(it.nombre) + '</td><td class="r">' + it.cant + ' x</td><td class="r">' + C.fmtCLP(it.precio * it.cant) + '</td></tr>';
    }).join('');
    $('#ticket-contenido').innerHTML =
      '<div class="papel" id="ticket-papel">' +
      '<h3 id="t-ticket">PITS DETAILING</h3><p class="c">Ticket de pedido</p><hr>' +
      '<p class="num-ticket">#' + p.id + '</p>' +
      '<p class="c">' + C.fmtFecha(p.creado) + '</p><hr>' +
      '<table><thead><tr><th>Producto</th><th class="r">Cant.</th><th class="r">Subtotal</th></tr></thead><tbody>' + filas + '</tbody></table><hr>' +
      '<div class="total"><span>TOTAL</span><span>' + C.fmtCLP(p.total) + '</span></div>' +
      '<div class="estado-t" id="ticket-estado">' + esc(Store.ESTADOS[p.estado].bodega.toUpperCase()) + '</div>' +
      '<p class="c" style="margin-top:.8em">Presenta este número en el mesón.<br>Demostración: sin valor comercial.</p></div>' +
      '<div class="acciones"><button type="button" class="btn btn-prim" data-acc="pdf">Descargar PDF</button>' +
      '<button type="button" class="btn btn-sec" data-acc="imprimir">Imprimir</button>' +
      '<button type="button" class="btn btn-sec" data-acc="ver-seguimiento">← Volver al seguimiento</button>' +
      '<button type="button" class="btn btn-prim" data-acc="finalizar">Finalizar operación</button></div>';
  }
  function descargarPdf() {
    var p = Store.obtener(st.pedidoId);
    if (!p) return;
    var cuerpo = {
      numero: p.id, fecha: C.fmtFecha(p.creado), estado: Store.ESTADOS[p.estado].bodega,
      items: p.items.map(function (i) { return { nombre: i.nombre, cantidad: i.cant, precio: i.precio }; })
    };
    aviso('Generando PDF…');
    fetch(new URL('../api/ticket', location.href), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cuerpo) })
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (d) {
        var a = document.createElement('a');
        a.href = new URL(d.pdf, location.origin).href; a.download = 'Ticket_' + p.id + '.pdf';
        document.body.appendChild(a); a.click(); a.remove();
        aviso('Ticket descargado');
      })
      .catch(function () {
        aviso('Sin conexión con el servidor: se abre la impresión (elige «Guardar como PDF»).');
        setTimeout(function () { window.print(); }, 700);
      });
  }

  /* ---------- reinicio ---------- */
  function reiniciarSesionCliente() {
    st.carrito = {}; st.pedidoId = null; st.estadoVisto = null; st.cat = C.CATEGORIAS[0].id;
    ir('bienvenida');
  }

  var tAviso = null;
  function aviso(txt) {
    var t = $('#toast'); t.textContent = txt; t.classList.add('visible');
    clearTimeout(tAviso); tAviso = setTimeout(function () { t.classList.remove('visible'); }, 3200);
  }

  /* ---------- eventos ---------- */
  document.addEventListener('click', function (ev) {
    var b = ev.target.closest('[data-acc]');
    if (!b || b.disabled) return;
    var id = b.getAttribute('data-id');
    switch (b.getAttribute('data-acc')) {
      case 'comenzar': ir('catalogo'); break;
      case 'cat': st.cat = b.getAttribute('data-cat'); renderTabs(); renderLista(); break;
      case 'mas': cambiar(id, 1); break;
      case 'menos': cambiar(id, -1); break;
      case 'quitar': delete st.carrito[id]; renderCarrito(); actualizarCuenta(); break;
      case 'ver-carrito': ir('carrito'); break;
      case 'volver-catalogo': ir('catalogo'); break;
      case 'confirmar': ir('resumen'); break;
      case 'volver-carrito': ir('carrito'); break;
      case 'enviar': enviarPedido(); break;
      case 'ver-ticket': ir('ticket'); break;
      case 'ver-seguimiento': ir('seguimiento'); break;
      case 'pdf': descargarPdf(); break;
      case 'imprimir': window.print(); break;
      case 'finalizar': reiniciarSesionCliente(); break;
    }
  });

  // Cambios hechos desde el panel de bodega (u otra pantalla): se reflejan sin recargar
  Store.suscribir(function () {
    if (st.pedidoId == null) return;
    var p = Store.obtener(st.pedidoId);
    if (!p) { reiniciarSesionCliente(); return; }           // la demo se reinició desde bodega
    var cambio = st.estadoVisto !== null && st.estadoVisto !== p.estado;
    if (st.vista === 'seguimiento') renderSeguimiento();
    if (st.vista === 'ticket') {
      var el = $('#ticket-estado');
      if (el) el.textContent = Store.ESTADOS[p.estado].bodega.toUpperCase();
    }
    if (cambio && p.estado === 2) chime();
    if (cambio && st.vista !== 'seguimiento') aviso(Store.ESTADOS[p.estado].cliente);
    st.estadoVisto = p.estado;
  });

  // Para el modo embed (dentro de la página): oculta el bisel
  if (/[?&]embed=1/.test(location.search)) document.documentElement.classList.add('embed');

  // Estado inicial
  ir('bienvenida');
})();
