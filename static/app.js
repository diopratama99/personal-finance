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
  const css = `.ripple{position:absolute;border-radius:50%;transform:scale(0);animation:ripple .6s linear;background:rgba(255,255,255,.6)}@keyframes ripple{to{transform:scale(4);opacity:0}}`;
  const s = document.createElement('style'); s.innerHTML = css; document.head.appendChild(s);
})();

// ---- Helper: warna chart mengikuti CSS variable --chart-bar
export function chartGradient(ctx, canvas){
  const rgb = getComputedStyle(document.documentElement).getPropertyValue('--chart-bar').trim() || '45,156,219';
  const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
  grad.addColorStop(0, `rgba(${rgb}, .55)`);
  grad.addColorStop(1, `rgba(${rgb}, .15)`);
  return grad;
}

