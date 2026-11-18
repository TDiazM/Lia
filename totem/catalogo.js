/*
 * Catálogo de ejemplo del tótem (productos ficticios) e ilustraciones SVG de producto.
 * No depende del chatbot ni del backend.
 */
(function (g) {
  'use strict';
  var NS = (g.PitsTotem = g.PitsTotem || {});

  var CATEGORIAS = [
    { id: 'shampoo', nombre: 'Shampoo para vehículos', corto: 'Shampoo', icono: '💧' },
    { id: 'ceras', nombre: 'Ceras y abrillantadores', corto: 'Ceras', icono: '✨' },
    { id: 'micro', nombre: 'Microfibras y accesorios', corto: 'Microfibras', icono: '🧽' },
    { id: 'limpieza', nombre: 'Productos de limpieza', corto: 'Limpieza', icono: '🧴' }
  ];

  var PRODUCTOS = [
    { id: 'sh1', cat: 'shampoo', nombre: 'Lumina Shampoo pH Neutro 1 L', desc: 'Espuma abundante que respeta ceras y selladores.', precio: 7990, tipo: 'botella', color: '#2f80a8' },
    { id: 'sh2', cat: 'shampoo', nombre: 'Lumina Shampoo Concentrado 500 ml', desc: 'Rinde hasta 1:200. Aroma cítrico.', precio: 5990, tipo: 'botella', color: '#d99a1f' },
    { id: 'sh3', cat: 'shampoo', nombre: 'Lumina Snow Foam 1 L', desc: 'Prelavado en espuma densa para hidrolavadora.', precio: 12990, tipo: 'botella', color: '#7a5ac8' },
    { id: 'sh4', cat: 'shampoo', nombre: 'Lumina Shampoo con Cera 1 L', desc: 'Lava y deja brillo hidrofóbico en un solo paso.', precio: 9990, tipo: 'botella', color: '#c9796a' },

    { id: 'ce1', cat: 'ceras', nombre: 'Lumina Cera en Pasta Carnauba 200 g', desc: 'Brillo profundo y protección de hasta 3 meses.', precio: 17990, tipo: 'tarro', color: '#a56a2a' },
    { id: 'ce2', cat: 'ceras', nombre: 'Lumina Cera Líquida Express 500 ml', desc: 'Aplicación rápida y sin residuos blancos.', precio: 8990, tipo: 'spray', color: '#d4a017' },
    { id: 'ce3', cat: 'ceras', nombre: 'Lumina Sellador Cerámico Spray 500 ml', desc: 'Protección hidrofóbica de 6 meses en minutos.', precio: 19990, tipo: 'spray', color: '#2c6fb0' },
    { id: 'ce4', cat: 'ceras', nombre: 'Lumina Abrillantador Rápido 500 ml', desc: 'Realza el brillo entre lavados.', precio: 9990, tipo: 'spray', color: '#4f9a63' },

    { id: 'mi1', cat: 'micro', nombre: 'Lumina Set 4 Paños Microfibra 40x40', desc: 'Suaves y sin pelusa, para pulido y secado.', precio: 6990, tipo: 'pano', color: '#3f8f6b' },
    { id: 'mi2', cat: 'micro', nombre: 'Lumina Toalla de Secado 90x60 cm', desc: 'Absorbe 10 veces su peso, sin dejar rayas.', precio: 15990, tipo: 'pano', color: '#c9796a' },
    { id: 'mi3', cat: 'micro', nombre: 'Lumina Aplicador de Espuma (3 un.)', desc: 'Para cera y sellador, no raya la pintura.', precio: 3490, tipo: 'esponja', color: '#d99a1f' },
    { id: 'mi4', cat: 'micro', nombre: 'Lumina Cepillo Suave para Llantas', desc: 'Cerdas firmes y mango ergonómico.', precio: 5490, tipo: 'cepillo', color: '#3f533e' },

    { id: 'li1', cat: 'limpieza', nombre: 'Lumina Limpiador de Vidrios 500 ml', desc: 'Sin rastros ni vaho. Apto para espejos.', precio: 4990, tipo: 'spray', color: '#3b9ec8' },
    { id: 'li2', cat: 'limpieza', nombre: 'Lumina Limpiador de Interiores 500 ml', desc: 'Tapiz, plásticos y cuero sin brillo grasoso.', precio: 6490, tipo: 'spray', color: '#8a6fb5' },
    { id: 'li3', cat: 'limpieza', nombre: 'Lumina Desengrasante Multiuso 5 L', desc: 'Para motor, chasis y suciedad pesada.', precio: 24990, tipo: 'bidon', color: '#5e7a5d' },
    { id: 'li4', cat: 'limpieza', nombre: 'Lumina Limpiador de Llantas 750 ml', desc: 'Disuelve el polvo de frenos sin frotar.', precio: 8490, tipo: 'botella', color: '#b5483a' }
  ];

  function porId(id) {
    for (var i = 0; i < PRODUCTOS.length; i++) if (PRODUCTOS[i].id === id) return PRODUCTOS[i];
    return null;
  }

  function fmtCLP(n) {
    return '$' + String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  function dos(n) { return (n < 10 ? '0' : '') + n; }
  function fmtFecha(iso) {
    var d = new Date(iso);
    return dos(d.getDate()) + '/' + dos(d.getMonth() + 1) + '/' + d.getFullYear() + ' ' + dos(d.getHours()) + ':' + dos(d.getMinutes());
  }
  function fmtHora(iso, conSegundos) {
    var d = new Date(iso);
    return dos(d.getHours()) + ':' + dos(d.getMinutes()) + (conSegundos ? ':' + dos(d.getSeconds()) : '');
  }

  // Aclara u oscurece un color #rrggbb
  function sombra(hex, amt) {
    var n = parseInt(hex.slice(1), 16);
    function c(v) { return Math.max(0, Math.min(255, v + amt)); }
    var r = c(n >> 16), gg = c((n >> 8) & 255), b = c(n & 255);
    return '#' + ((1 << 24) + (r << 16) + (gg << 8) + b).toString(16).slice(1);
  }

  function etiqueta(x, y, w, h, sub) {
    return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="5" fill="#fff" fill-opacity=".93"/>' +
      '<text x="' + (x + w / 2) + '" y="' + (y + h / 2 - 1) + '" text-anchor="middle" font-family="system-ui,sans-serif" font-size="10" font-weight="800" letter-spacing="1.2" fill="#283627">LUMINA</text>' +
      '<text x="' + (x + w / 2) + '" y="' + (y + h / 2 + 11) + '" text-anchor="middle" font-family="system-ui,sans-serif" font-size="7.5" fill="#5e7a5d">' + sub + '</text>';
  }

  // Ilustración SVG de un producto (sin imágenes externas, funciona sin conexión)
  function imagenSVG(p) {
    var id = 'g' + p.id, c = p.color, osc = sombra(c, -34), cla = sombra(c, 30), f = '';
    var grad = 'url(#' + id + 'b)';
    switch (p.tipo) {
      case 'botella':
        f = '<rect x="86" y="34" width="28" height="17" rx="4" fill="' + osc + '"/>' +
          '<rect x="90" y="49" width="20" height="24" fill="' + cla + '"/>' +
          '<path d="M68 86Q68 70 88 70H112Q132 70 132 86V162Q132 173 121 173H79Q68 173 68 162Z" fill="' + grad + '"/>' +
          etiqueta(75, 98, 50, 54, 'AUTO CARE') +
          '<rect x="73" y="84" width="6" height="80" rx="3" fill="#fff" fill-opacity=".25"/>';
        break;
      case 'bidon':
        f = '<path d="M56 80Q56 64 72 64H128Q144 64 144 80V164Q144 173 135 173H65Q56 173 56 164Z" fill="' + grad + '"/>' +
          '<rect x="64" y="50" width="28" height="17" rx="4" fill="' + osc + '"/>' +
          '<path d="M118 64V54Q118 46 126 46H134Q142 46 142 54V66" fill="none" stroke="' + osc + '" stroke-width="7" stroke-linecap="round"/>' +
          etiqueta(68, 98, 64, 56, '5 LITROS') +
          '<rect x="62" y="82" width="6" height="82" rx="3" fill="#fff" fill-opacity=".25"/>';
        break;
      case 'tarro':
        f = '<path d="M44 112H156V160Q156 173 143 173H57Q44 173 44 160Z" fill="' + grad + '"/>' +
          '<rect x="42" y="92" width="116" height="26" rx="7" fill="' + osc + '"/>' +
          '<rect x="46" y="96" width="108" height="5" rx="2.5" fill="#fff" fill-opacity=".25"/>' +
          etiqueta(58, 124, 84, 38, 'PASTA 200 G');
        break;
      case 'spray':
        f = '<rect x="82" y="54" width="38" height="22" rx="6" fill="' + osc + '"/>' +
          '<rect x="114" y="58" width="24" height="10" rx="3" fill="' + osc + '"/>' +
          '<path d="M97 76Q88 86 93 98H105Z" fill="#2c2c2c"/>' +
          '<rect x="88" y="74" width="24" height="18" fill="' + cla + '"/>' +
          '<path d="M70 104Q70 90 84 90H116Q130 90 130 104V162Q130 173 119 173H81Q70 173 70 162Z" fill="' + grad + '"/>' +
          etiqueta(76, 108, 48, 48, 'SPRAY') +
          '<rect x="75" y="94" width="6" height="70" rx="3" fill="#fff" fill-opacity=".25"/>';
        break;
      case 'pano':
        f = '<rect x="50" y="130" width="100" height="28" rx="7" fill="' + osc + '"/>' +
          '<rect x="46" y="107" width="100" height="28" rx="7" fill="' + c + '"/>' +
          '<rect x="54" y="84" width="100" height="28" rx="7" fill="' + cla + '"/>' +
          '<path d="M62 98H146M58 121H138M60 144H142" stroke="#fff" stroke-opacity=".55" stroke-width="2" stroke-dasharray="3 5"/>' +
          '<rect x="108" y="116" width="42" height="18" rx="4" fill="#fff" fill-opacity=".93"/>' +
          '<text x="129" y="128" text-anchor="middle" font-family="system-ui,sans-serif" font-size="8" font-weight="800" letter-spacing="1" fill="#283627">LUMINA</text>';
        break;
      case 'esponja':
        f = '<rect x="58" y="126" width="84" height="40" rx="16" fill="' + osc + '"/>' +
          '<rect x="58" y="108" width="84" height="40" rx="16" fill="' + c + '"/>' +
          '<rect x="58" y="90" width="84" height="40" rx="16" fill="' + cla + '"/>' +
          '<g fill="#fff" fill-opacity=".45"><circle cx="78" cy="106" r="3"/><circle cx="100" cy="112" r="3"/><circle cx="122" cy="104" r="3"/><circle cx="88" cy="122" r="2.5"/><circle cx="112" cy="124" r="2.5"/></g>';
        break;
      case 'cepillo':
        f = '<g transform="translate(100 108) rotate(-35) scale(.82) translate(-112 -109)">' +
          '<rect x="36" y="99" width="104" height="20" rx="10" fill="' + c + '"/>' +
          '<rect x="46" y="104" width="60" height="4" rx="2" fill="#fff" fill-opacity=".3"/>' +
          '<rect x="132" y="88" width="46" height="42" rx="7" fill="' + osc + '"/>' +
          '<rect x="174" y="90" width="14" height="38" rx="3" fill="#efe3c0"/>' +
          '<path d="M178 94V124M182 94V124M186 94V124" stroke="#c9b98a" stroke-width="1.2"/></g>';
        break;
    }
    return '<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="' + p.nombre + '">' +
      '<defs><linearGradient id="' + id + 'b" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stop-color="' + cla + '"/><stop offset=".55" stop-color="' + c + '"/><stop offset="1" stop-color="' + osc + '"/></linearGradient>' +
      '<radialGradient id="' + id + 'f" cx=".5" cy=".38" r=".85"><stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#dcebd6"/></radialGradient></defs>' +
      '<rect width="200" height="200" fill="url(#' + id + 'f)"/>' +
      '<ellipse cx="100" cy="176" rx="54" ry="8" fill="rgba(40,54,39,.18)"/>' + f + '</svg>';
  }

  NS.Catalogo = { CATEGORIAS: CATEGORIAS, PRODUCTOS: PRODUCTOS, porId: porId, fmtCLP: fmtCLP, fmtFecha: fmtFecha, fmtHora: fmtHora, imagenSVG: imagenSVG };
})(window);
