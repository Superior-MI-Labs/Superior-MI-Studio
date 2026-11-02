/* Decorative neural graph. No libraries, requests, tracking, or UI state. */
(() => {
  const canvas = document.getElementById('neural-background');
  if (!canvas || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  let width = 0, height = 0, nodes = [], active = false, raf = 0, previous = 0;
  let pointer = { x: -1000, y: -1000 };
  const seed = n => (Math.sin(n * 127.1 + 41.7) * 43758.5453) % 1;
  const random = n => Math.abs(seed(n));
  function resize() {
    width = canvas.clientWidth; height = canvas.clientHeight;
    const scale = Math.min(window.devicePixelRatio || 1, 1.5);
    canvas.width = Math.round(width * scale); canvas.height = Math.round(height * scale);
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    const count = width < 700 ? 16 : 34;
    nodes = Array.from({ length: count }, (_, i) => ({
      x: random(i * 7 + 1) * width, y: random(i * 7 + 2) * height,
      phase: random(i * 7 + 3) * Math.PI * 2, amp: 2 + random(i * 7 + 4) * 6,
    }));
  }
  function draw(now) {
    if (!active) { raf = 0; return; }
    raf = window.requestAnimationFrame(draw);
    if (now - previous < 34) return;
    previous = now;
    ctx.clearRect(0, 0, width, height);
    const t = now * .0003;
    const positions = nodes.map(n => ({ x: n.x + Math.sin(t + n.phase) * n.amp, y: n.y + Math.cos(t + n.phase) * n.amp }));
    for (let i = 0; i < positions.length; i++) {
      const a = positions[i];
      for (let j = i + 1; j < positions.length; j++) {
        const b = positions[j]; const dist = Math.hypot(a.x - b.x, a.y - b.y);
        if (dist > 185) continue;
        const proximity = Math.max(0, 1 - Math.min(Math.hypot(a.x - pointer.x, a.y - pointer.y), 300) / 300);
        ctx.strokeStyle = `rgba(76, 191, 223, ${(.035 + proximity * .1) * (1 - dist / 185)})`;
        ctx.lineWidth = .8; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
      ctx.fillStyle = 'rgba(85, 192, 219, .2)'; ctx.beginPath(); ctx.arc(a.x, a.y, 1.5, 0, Math.PI * 2); ctx.fill();
    }
  }
  const visible = new IntersectionObserver(entries => {
    active = entries[0].isIntersecting && !document.hidden;
    if (active && !raf) raf = window.requestAnimationFrame(draw);
  });
  visible.observe(canvas);
  window.addEventListener('pointermove', e => { pointer.x = e.clientX; pointer.y = e.clientY + window.scrollY; }, { passive: true });
  window.addEventListener('resize', resize, { passive: true });
  document.addEventListener('visibilitychange', () => { active = !document.hidden && canvas.getBoundingClientRect().bottom > 0; if (active && !raf) raf = requestAnimationFrame(draw); });
  resize();
})();
