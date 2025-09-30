// Dark mode toggle (disimpan di localStorage)
(function(){
  const root = document.documentElement;
  const btn = document.getElementById('themeToggle');
  if(!btn) return;
  const saved = localStorage.getItem('theme');
  if(saved) document.documentElement.setAttribute('data-theme', saved);
  btn.onclick = () => {
    const curr = document.documentElement.getAttribute('data-theme') || 'light';
    const next = curr === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
  };
})();

// Count up numbers (smooth)
(function(){
  const els = document.querySelectorAll('.count-up');
  els.forEach(el=>{
    const target = Number(el.getAttribute('data-target')||0);
    let curr = 0;
    const inc = target/40; // 40 steps
    const timer = setInterval(()=>{
      curr += inc;
      if((inc>=0 && curr>=target) || (inc<0 && curr<=target)) { curr = target; clearInterval(timer); }
      const val = Math.round(curr).toLocaleString('id-ID');
      el.innerText = (target<0?'-':'') + 'Rp ' + val.replace('-', '');
    }, 16);
  });
})();

// ---- Ripple effect untuk semua .btn-ripple (termasuk navbar)
(function(){
  const addRipple = (e)=>{
    const btn = e.currentTarget;
    const circle = document.createElement('span');
    const rect = btn.getBoundingClientRect();
    const d = Math.max(rect.width, rect.height);
    circle.style.width = circle.style.height = d + 'px';
    circle.style.left = (e.clientX - rect.left - d/2) + 'px';
    circle.style.top  = (e.clientY - rect.top  - d/2) + 'px';
    circle.className = 'ripple';
    btn.appendChild(circle);
    setTimeout(()=>circle.remove(), 600);
  };
  document.querySelectorAll('.btn-ripple').forEach(b=>{
    b.style.position='relative';
    b.style.overflow='hidden';
    b.addEventListener('click', addRipple);
  });
})();

// Gunakan Montserrat untuk chart
if (window.Chart) {
  Chart.defaults.font.family = 'Montserrat, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
  Chart.defaults.font.size = 12;
}

// style untuk ripple (inject ke head satu kali)
(function(){
  const css = `.ripple{position:absolute;border-radius:50%;transition:transform .6s,opacity .6s;transform:scale(0);opacity:.5;background:radial-gradient(circle,rgba(255,255,255,.8) 10%,rgba(255,255,255,.6) 40%,rgba(255,255,255,.0) 70%)}.ripple{animation:ripple .6s ease-out}.btn-ripple{position:relative;overflow:hidden}@keyframes ripple{to{transform:scale(4);opacity:0}}`;
  const s = document.createElement('style');
  s.innerHTML = css;                  // ⟵ FIX: pakai 'css', bukan 'cs'
  document.head.appendChild(s);
})();

// inisialisasi ripple untuk semua .btn
document.addEventListener('click', function(e){
  const btn = e.target.closest('.btn, .btn-ripple, [data-ripple]');
  if (!btn) return;

  const rect = btn.getBoundingClientRect();
  const ripple = document.createElement('span');
  ripple.className = 'ripple';
  const size = Math.max(rect.width, rect.height);
  ripple.style.width = ripple.style.height = size + 'px';
  ripple.style.left = (e.clientX - rect.left - size/2) + 'px';
  ripple.style.top  = (e.clientY - rect.top  - size/2) + 'px';

  btn.classList.add('btn-ripple');
  btn.appendChild(ripple);
  setTimeout(() => ripple.remove(), 650);
});

// ---- Helper: warna chart mengikuti CSS variable --chart-bar
window.chartGradient = function(ctx, canvas){
  const rgb = getComputedStyle(document.documentElement).getPropertyValue('--chart-bar').trim() || '45,156,219';
  const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
  grad.addColorStop(0, `rgba(${rgb}, .55)`);
  grad.addColorStop(1, `rgba(${rgb}, .15)`);
  return grad;
};

// Tutup offcanvas setelah klik link
document.addEventListener('click', function(e){
  const link = e.target.closest('[data-bs-dismiss=offcanvas], .offcanvas a');
  const canvasEl = document.querySelector('.offcanvas.show');
  if(link && canvasEl && window.bootstrap){
    const offcanvas = bootstrap.Offcanvas.getInstance(canvasEl);
    if(offcanvas) offcanvas.hide();
  }
});

// Page enter animation
document.addEventListener('DOMContentLoaded', () => {
  const main = document.querySelector('main');
  if(main){ requestAnimationFrame(()=> main.classList.add('page-enter')); }
});

// Page leave animation untuk link internal
document.addEventListener('click', (e) => {
  const a = e.target.closest('a[href]');
  if(!a) return;

  const url = new URL(a.href, location.href);
  const sameOrigin = url.origin === location.origin;

  // Skip: open new tab / download / anchors / tel / mail / data-no-transition
  if (!sameOrigin || a.target === '_blank' || a.hasAttribute('download') ||
      a.getAttribute('href').startsWith('#') ||
      /^mailto:|^tel:/.test(a.getAttribute('href')) ||
      a.hasAttribute('data-no-transition')) {
    return;
  }

  // Hindari cegah form submit
  if (a.closest('form')) return;

  e.preventDefault();
  document.body.classList.add('page-leave');
  setTimeout(()=> location.href = a.href, 180);
});

