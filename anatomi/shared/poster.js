// Shared builder for the Swedish anatomy posters.
//
// Each poster.html defines window.POSTER and then loads this file:
//
// window.POSTER = {
//   number: 1,                         // 1-4, shown in the kicker ("Anatomi 1/4")
//   title: 'Kroppens delar',           // Swedish title
//   subtitle: 'Body parts',            // small English gloss of the title
//   image: {
//     src: 'clean.png',                // label-free illustration (same folder)
//     crop: [x0, y0, x1, y1],          // region of the source image to show, in SOURCE px
//     x: 300, y: 10, width: 480,       // where the crop goes, in FIGURE px (figure is 1080 x 1500)
//   },
//   labelX: { L: 250, R: 830 },        // L = right edge of left-column labels, R = left edge of right-column labels (figure px)
//   labels: [
//     // art: 'en' | 'ett'; word: Swedish noun (indefinite singular); en: English (QA only, not drawn)
//     // side: 'L' | 'R'; y: vertical centre of the label in FIGURE px
//     // ax, ay: the point the leader line touches, in SOURCE image px
//     // optional lx: override labelX for this one label
//     { art: 'ett', word: 'huvud', en: 'head', side: 'R', y: 60, ax: 560, ay: 120 },
//   ],
//   note: 'Obs! <b class="ett">ett ben</b> = a leg – and also a bone.',  // footer note (HTML, optional)
// };
//
// Render: node tools/render.js anatomi/<cat>/poster.html anatomi/<cat>/<file>.png
// Debug grid with coordinates: open/render anatomi/<cat>/poster.html?grid
// Layout problems (overlaps, labels off the poster, leaders crossing labels)
// are printed as console warnings, which tools/render.js forwards.

(function () {
  const P = window.POSTER;
  const FIG_W = 1080, FIG_H = 1500, FIG_TOP = 200;
  const GAP = 12; // space between a label's edge and the start of its leader line

  const el = (tag, cls, html) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  };
  const svgEl = (tag, attrs) => {
    const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  };

  const poster = el('div', 'poster');
  document.body.appendChild(poster);

  // Header
  const header = el('div', 'header');
  const left = el('div');
  left.appendChild(el('div', 'kicker', `Anatomi ${P.number}/4`));
  left.appendChild(el('div', 'title', P.title));
  left.appendChild(el('div', 'subtitle', P.subtitle));
  header.appendChild(left);
  const legend = el('div', 'legend');
  legend.appendChild(el('div', 'chip en', '<b>en</b> en-ord'));
  legend.appendChild(el('div', 'chip ett', '<b>ett</b> ett-ord'));
  header.appendChild(legend);
  poster.appendChild(header);

  // Figure
  const fig = el('div', 'figure');
  poster.appendChild(fig);
  const im = P.image;
  const imgEl = new Image();
  const ready = [];
  ready.push(new Promise((res, rej) => { imgEl.onload = res; imgEl.onerror = () => rej(new Error('image failed: ' + im.src)); }));
  imgEl.src = im.src;

  // Footer
  const footer = el('div', 'footer');
  footer.appendChild(el('div', 'note', P.note || ''));
  footer.appendChild(el('div', 'series', 'Svenska · Människokroppen'));
  poster.appendChild(footer);

  ready.push(document.fonts.ready);

  Promise.all(ready).then(() => {
    const nw = imgEl.naturalWidth, nh = imgEl.naturalHeight;
    const [x0, y0, x1, y1] = im.crop || [0, 0, nw, nh];
    const s = im.width / (x1 - x0);
    const crop = el('div', 'crop');
    Object.assign(crop.style, {
      left: im.x + 'px', top: im.y + 'px',
      width: (x1 - x0) * s + 'px', height: (y1 - y0) * s + 'px',
    });
    Object.assign(imgEl.style, { width: nw * s + 'px', height: nh * s + 'px', left: -x0 * s + 'px', top: -y0 * s + 'px' });
    crop.appendChild(imgEl);
    fig.appendChild(crop);
    const toFig = (ax, ay) => [im.x + (ax - x0) * s, im.y + (ay - y0) * s];

    const imgBottom = im.y + (y1 - y0) * s;
    if (im.y < 0 || imgBottom > FIG_H || im.x < 0 || im.x + (x1 - x0) * s > FIG_W)
      console.warn(`image placement exceeds figure area (x ${im.x}..${(im.x + (x1 - x0) * s).toFixed(0)}, y ${im.y}..${imgBottom.toFixed(0)}; area is 1080 x 1500)`);

    // Leader lines sit above the image and below the labels (labels are appended after).
    const svg = svgEl('svg', { class: 'leaders', viewBox: `0 0 ${FIG_W} ${FIG_H}` });
    fig.appendChild(svg);

    const boxes = [];
    for (const L of P.labels) {
      const lab = el('div', 'label ' + L.art, `<span class="art">${L.art}</span>${L.word}`);
      fig.appendChild(lab);
      const w = lab.offsetWidth, h = lab.offsetHeight;
      const edge = L.lx != null ? L.lx : P.labelX[L.side];
      const left = L.side === 'L' ? edge - w : edge;
      const top = L.y - h / 2;
      lab.style.left = left + 'px';
      lab.style.top = top + 'px';
      const box = { L, left, top, right: left + w, bottom: top + h };
      boxes.push(box);

      const [tx, ty] = toFig(L.ax, L.ay);
      const sx = L.side === 'L' ? box.right + GAP : box.left - GAP;
      box.seg = [sx, L.y, tx, ty];
      svg.appendChild(svgEl('line', { x1: sx, y1: L.y, x2: tx, y2: ty }));
      svg.appendChild(svgEl('circle', { cx: tx, cy: ty, r: 5.5 }));
    }

    // ---- layout checks ----
    const name = (b) => `"${b.L.art} ${b.L.word}"`;
    const pad = 4;
    for (const b of boxes) {
      if (b.left < 24 || b.right > FIG_W - 24 || b.top < 0 || b.bottom > FIG_H)
        console.warn(`label ${name(b)} is outside the safe area (left ${b.left.toFixed(0)}, right ${b.right.toFixed(0)}, top ${b.top.toFixed(0)})`);
      const [ax, ay] = toFig(b.L.ax, b.L.ay);
      if (ax < im.x || ay < im.y || ay > imgBottom || ax > im.x + (x1 - x0) * s)
        console.warn(`anchor of ${name(b)} lies outside the shown image`);
    }
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i], b = boxes[j];
        if (a.left < b.right + pad && b.left < a.right + pad && a.top < b.bottom + pad && b.top < a.bottom + pad)
          console.warn(`labels overlap: ${name(a)} and ${name(b)}`);
      }
    }
    const segHitsBox = ([xa, ya, xb, yb], r) => {
      // sample the segment; good enough for a layout lint
      for (let t = 0; t <= 1; t += 0.01) {
        const x = xa + (xb - xa) * t, y = ya + (yb - ya) * t;
        if (x > r.left && x < r.right && y > r.top && y < r.bottom) return true;
      }
      return false;
    };
    for (const a of boxes) for (const b of boxes) {
      if (a !== b && segHitsBox(a.seg, b)) console.warn(`leader of ${name(a)} crosses label ${name(b)}`);
    }
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) {
      const [p1x, p1y, p2x, p2y] = boxes[i].seg, [p3x, p3y, p4x, p4y] = boxes[j].seg;
      const d = (p4y - p3y) * (p2x - p1x) - (p4x - p3x) * (p2y - p1y);
      if (d === 0) continue;
      const ua = ((p4x - p3x) * (p1y - p3y) - (p4y - p3y) * (p1x - p3x)) / d;
      const ub = ((p2x - p1x) * (p1y - p3y) - (p2y - p1y) * (p1x - p3x)) / d;
      if (ua > 0.001 && ua < 0.999 && ub > 0.001 && ub < 0.999)
        console.warn(`leader lines cross: ${name(boxes[i])} and ${name(boxes[j])}`);
    }

    if (/[?&]grid\b/.test(location.search)) {
      const g = svgEl('svg', { class: 'grid', viewBox: '0 0 1080 1800', width: 1080, height: 1800 });
      for (let x = 0; x <= 1080; x += 50) {
        g.appendChild(svgEl('line', { x1: x, y1: 0, x2: x, y2: 1800 }));
        if (x % 100 === 0) { const t = svgEl('text', { x: x + 2, y: FIG_TOP + 12 }); t.textContent = x; g.appendChild(t); }
      }
      for (let y = FIG_TOP; y <= FIG_TOP + FIG_H; y += 50) {
        g.appendChild(svgEl('line', { x1: 0, y1: y, x2: 1080, y2: y }));
        if ((y - FIG_TOP) % 100 === 0) { const t = svgEl('text', { x: 2, y: y - 2 }); t.textContent = 'fig y ' + (y - FIG_TOP); g.appendChild(t); }
      }
      poster.appendChild(g);
    }
    window.__posterReady = true;
  }).catch((e) => { console.error(e.message); window.__posterReady = true; });
})();
