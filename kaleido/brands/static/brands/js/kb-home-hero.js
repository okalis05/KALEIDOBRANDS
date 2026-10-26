(() => {
  const stage = document.getElementById('kbCampaignStage');
  if (!stage) return;
  const slides = [...stage.querySelectorAll('[data-kb-slide]')];
  const dots = [...stage.querySelectorAll('[data-kb-dot]')];
  const products = [...stage.querySelectorAll('[data-kb-product]')];
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let current = 0, productIndex = 0, timer;
  const setSlide = index => {
    current = (index + slides.length) % slides.length;
    slides.forEach((slide, i) => {
      const active = i === current;
      slide.classList.toggle('is-active', active);
      slide.setAttribute('aria-hidden', String(!active));
      if ('inert' in slide) slide.inert = !active;
    });
    dots.forEach((dot, i) => {
      dot.classList.toggle('is-active', i === current);
      dot.setAttribute('aria-current', String(i === current));
    });
    if (current === 2 && products.length) {
      products.forEach((product, i) => {
        const active = i === productIndex % products.length;
        product.classList.toggle('is-active', active);
        product.tabIndex = active ? 0 : -1;
      });
      productIndex++;
    }
  };
  const stop = () => clearInterval(timer);
  const start = () => { stop(); if (!reduced) timer = setInterval(() => setSlide(current + 1), 6000); };
  stage.querySelector('[data-kb-prev]').addEventListener('click', () => { setSlide(current - 1); start(); });
  stage.querySelector('[data-kb-next]').addEventListener('click', () => { setSlide(current + 1); start(); });
  dots.forEach(dot => dot.addEventListener('click', () => { setSlide(Number(dot.dataset.kbDot)); start(); }));
  stage.addEventListener('mouseenter', stop);
  stage.addEventListener('mouseleave', start);
  stage.addEventListener('focusin', stop);
  stage.addEventListener('focusout', event => { if (!stage.contains(event.relatedTarget)) start(); });
  document.addEventListener('visibilitychange', () => document.hidden ? stop() : start());
  setSlide(0); start();
})();
