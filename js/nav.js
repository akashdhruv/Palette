// Palette - Navigation component
// Injects a nav bar with back link at the top of calculator pages
(function() {
  const title = document.title.replace(' - Palette', '').replace('Calculator', '').trim();
  const nav = document.createElement('div');
  nav.id = 'palette-nav';
  nav.innerHTML = `<a href="../index.html">&larr; Palette</a><span class="nav-title">${title}</span>`;
  document.body.prepend(nav);
})();
