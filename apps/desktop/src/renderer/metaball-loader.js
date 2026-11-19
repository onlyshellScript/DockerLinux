// metaball-loader.js: MetaballLoader, el único indicador visual de carga de SIGOS.
// Tres círculos 2D sólidos que parten fusionados, se separan, cruzan sus trayectorias y vuelven a fusionarse
// (efecto metaball: desenfoque + umbral alfa en un filtro SVG). Réplica del prototipo aprobado.
//
// - Una sola definición del filtro (#sigos-goo) en el documento, compartida por todas las instancias.
// - Un solo ciclo requestAnimationFrame para todas las instancias visibles: se detiene solo cuando no queda
//   ninguna en el DOM (colección viva) y se reactiva al insertar una nueva (MutationObserver). Sin fugas.
// - prefers-reduced-motion: los tres círculos quedan fusionados y quietos (se conserva el mensaje).
// - El color es currentColor: el contenedor decide (marca en vistas, texto del botón en botones).
(function () {
  const NS = 'http://www.w3.org/2000/svg';
  const CX = 115;
  const CY = 80;
  const R = 25;
  const DURATION = 2400;
  // Posiciones relativas de cada círculo por fase; empiezan y terminan superpuestas (un único círculo).
  const PHASES = [
    { t: 0.00, p: [[0, 0], [0, 0], [0, 0]] },
    { t: 0.18, p: [[-13, 0], [0, 0], [13, 0]] },
    { t: 0.38, p: [[-48, -3], [0, 24], [48, -3]] },
    { t: 0.58, p: [[-28, 19], [30, -18], [-2, -30]] },
    { t: 0.76, p: [[-13, 0], [0, 0], [13, 0]] },
    { t: 1.00, p: [[0, 0], [0, 0], [0, 0]] },
  ];
  const SIZES = { xs: 44, sm: 64, md: 96, lg: 150 };

  const smoothstep = (x) => x * x * (3 - 2 * x);

  // positionsAt(progress): coordenadas absolutas de los tres círculos en un punto del ciclo [0, 1).
  function positionsAt(progress) {
    let a = PHASES[0];
    let b = PHASES[PHASES.length - 1];
    for (let i = 0; i < PHASES.length - 1; i++) {
      if (progress >= PHASES[i].t && progress <= PHASES[i + 1].t) { a = PHASES[i]; b = PHASES[i + 1]; break; }
    }
    const mix = smoothstep(Math.max(0, Math.min(1, (progress - a.t) / (b.t - a.t))));
    return a.p.map((pa, i) => [CX + pa[0] + (b.p[i][0] - pa[0]) * mix, CY + pa[1] + (b.p[i][1] - pa[1]) * mix]);
  }

  // ensureDefs(): inserta una sola vez el filtro metaball compartido.
  function ensureDefs() {
    if (document.getElementById('sigos-goo')) return;
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('width', '0');
    svg.setAttribute('height', '0');
    svg.setAttribute('aria-hidden', 'true');
    svg.style.position = 'absolute';
    svg.innerHTML = `<defs><filter id="sigos-goo" x="-50%" y="-50%" width="200%" height="200%" color-interpolation-filters="sRGB">
      <feGaussianBlur in="SourceGraphic" stdDeviation="6.5" result="blur"/>
      <feColorMatrix in="blur" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 24 -11"/>
    </filter></defs>`;
    (document.body || document.documentElement).appendChild(svg);
  }

  // markup({ size }): HTML de una instancia. Decorativa (aria-hidden): el mensaje accesible lo da su contenedor.
  function markup({ size = 'md' } = {}) {
    const w = SIZES[size] || SIZES.md;
    const c = `<circle class="mb-ball" cx="${CX}" cy="${CY}" r="${R}"/>`;
    return `<svg class="mb mb--${size}" viewBox="0 0 230 160" width="${w}" height="${Math.round(w * 160 / 230)}" aria-hidden="true" focusable="false"><g filter="url(#sigos-goo)">${c}${c}${c}</g></svg>`;
  }

  // element(opts): igual que markup() pero como nodo DOM.
  function element(opts) {
    const tpl = document.createElement('template');
    tpl.innerHTML = markup(opts);
    return tpl.content.firstElementChild;
  }

  // ---- ciclo compartido ----
  const live = document.getElementsByClassName('mb'); // colección viva: refleja altas y bajas sin registro manual
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  let rafId = 0;

  function place(svg, pos) {
    const circles = svg.getElementsByTagName('circle');
    for (let i = 0; i < 3 && i < circles.length; i++) {
      circles[i].setAttribute('cx', pos[i][0].toFixed(2));
      circles[i].setAttribute('cy', pos[i][1].toFixed(2));
    }
  }

  function frame(now) {
    rafId = 0;
    if (!live.length || reduce.matches) return; // nada que animar: el ciclo se detiene
    const pos = positionsAt((now % DURATION) / DURATION);
    for (let i = 0; i < live.length; i++) place(live[i], pos);
    rafId = requestAnimationFrame(frame);
  }

  function wake() {
    if (rafId || !live.length) return;
    if (reduce.matches) {
      const still = positionsAt(0);
      for (let i = 0; i < live.length; i++) place(live[i], still);
      return;
    }
    rafId = requestAnimationFrame(frame);
  }

  function stop() { if (rafId) { cancelAnimationFrame(rafId); rafId = 0; } }

  function init() {
    ensureDefs();
    // Reactiva el ciclo al aparecer una instancia nueva (las vistas insertan HTML como texto).
    new MutationObserver(() => { if (!rafId && live.length) wake(); }).observe(document.body, { childList: true, subtree: true });
    reduce.addEventListener('change', () => { stop(); wake(); });
    wake();
  }

  if (document.body) init(); else document.addEventListener('DOMContentLoaded', init, { once: true });

  window.MetaballLoader = Object.freeze({ markup, element, positionsAt, _isRunning: () => !!rafId });
})();
