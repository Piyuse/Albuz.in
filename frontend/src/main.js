import './style.css';
import { albums } from './albums.js';
import { createAlbumGallery } from './shelf-gallery.js';
import { createAlbumReader } from './album-reader.js';
import './warm-theme.css';

const categories = ['All memories', 'Travel', 'Everyday', 'Together'];
const category = card => card.category;
let gallery, selectedCard = albums[0], tooltipWidth = 0;
window.addEventListener('resize', () => { tooltipWidth = 0; });

document.querySelector('#app').innerHTML = `
  <main class="collection">
    <header class="site-header">
      <button class="index-trigger">View all albums</button>
      <div class="brand"><h1>Stills</h1><p>A home for memories</p></div>
      <span class="header-spacer" aria-hidden="true"></span>
    </header>
    <nav class="category-tabs" aria-label="Filter memories">${categories.map((label, index) => `<button data-category="${label}" aria-pressed="${index === 0}">${label}</button>`).join('')}</nav>
    <section class="gallery-stage" aria-label="Animated memory books. Swipe, drag, or scroll to browse. Click a book to view its photos." tabindex="0">
      <div id="album-gallery"></div><div class="gallery-loading" role="status">Gathering your memories</div>
      <div class="stage-caption"><span class="interaction-hint">DRAG OR SCROLL TO EXPLORE <span>·</span> CLICK A BOOK TO OPEN</span></div>
      <div class="book-tooltip" aria-hidden="true"><strong></strong><span>OPEN ALBUM ↗</span></div>
      <button class="shelf-arrow shelf-arrow-prev" type="button" aria-label="Previous album">‹</button>
      <button class="shelf-arrow shelf-arrow-next" type="button" aria-label="Next album">›</button>
      <span class="sr-only current-album" aria-live="polite">Summer in Italy</span>
    </section>
  </main>
  <dialog class="album-index" aria-labelledby="index-title"><header><div><span class="eyebrow">YOUR COLLECTION</span><h2 id="index-title">Every memory.</h2></div><button class="close-index" aria-label="Close album collection">×</button></header><label class="search-box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/></svg><input type="search" placeholder="Find a place, a person, a memory…" aria-label="Search memory albums"/></label><div class="index-grid"></div><p class="no-results" hidden>No memories found. Try another search.</p><p class="index-note">Sample memories waiting to become yours.</p></dialog>`;

const indexDialog = document.querySelector('.album-index');
const reader = createAlbumReader({ onOpen: () => gallery?.setActive(false), onClose: () => gallery?.setActive(true) });
function openCard(card) { if (indexDialog.open) indexDialog.close(); reader.open(card); }
function renderIndex() {
  const query = indexDialog.querySelector('input').value.trim().toLowerCase();
  const matches = albums.filter(card => `${card.title} ${card.year} ${category(card)}`.toLowerCase().includes(query));
  indexDialog.querySelector('.index-grid').innerHTML = matches.map(card => `<button class="index-card" data-card="${card.id}"><span class="index-card-face" style="--card:${card.color}"><span class="index-mark">Stills</span><img src="${card.photo}" alt=""/><span class="index-card-title">${card.title}</span><span class="index-year">${card.year}</span></span><strong>${card.title}</strong><small>${category(card)} · ${card.year}</small></button>`).join('');
  indexDialog.querySelector('.no-results').hidden = matches.length > 0;
}
document.querySelector('.index-trigger').addEventListener('click', () => { renderIndex(); gallery?.setActive(false); indexDialog.showModal(); });
document.querySelector('.close-index').addEventListener('click', () => indexDialog.close());
indexDialog.addEventListener('close', () => { if (!reader.isOpen) gallery?.setActive(true); });
indexDialog.querySelector('input').addEventListener('input', renderIndex);
indexDialog.addEventListener('click', event => { const button = event.target.closest('[data-card]'); if (button) openCard(albums[Number(button.dataset.card)]); });
document.querySelector('.shelf-arrow-prev').addEventListener('click', () => gallery?.step(-1));
document.querySelector('.shelf-arrow-next').addEventListener('click', () => gallery?.step(1));
document.querySelectorAll('[data-category]').forEach(button => button.addEventListener('click', () => {
  const filtered = albums.filter(card => button.dataset.category === 'All memories' || category(card) === button.dataset.category);
  document.querySelectorAll('[data-category]').forEach(tab => tab.setAttribute('aria-pressed', String(tab === button)));
  gallery?.setAlbums(filtered);
}));
try {
  gallery = createAlbumGallery(document.querySelector('#album-gallery'), albums, {
    onReady: () => { document.querySelector('.gallery-loading')?.remove(); document.querySelector('.collection').classList.add('ready'); },
    onSelect: openCard,
    onChange: card => {
      selectedCard = card;
      document.querySelector('.current-album').textContent = card.title;
    },
    onHover: (card, position) => {
      const tooltip = document.querySelector('.book-tooltip');
      tooltip.classList.toggle('is-visible', Boolean(card));
      if (!card) return;
      const label = tooltip.querySelector('strong');
      if (label.textContent !== card.title) { label.textContent = card.title; tooltipWidth = 0; }
      if (!tooltipWidth) tooltipWidth = tooltip.offsetWidth;
      const halfWidth = tooltipWidth / 2;
      const stageWidth = document.querySelector('.gallery-stage').clientWidth;
      tooltip.style.left = `${Math.max(halfWidth + 10, Math.min(stageWidth - halfWidth - 10, position.x))}px`;
      tooltip.style.top = `${position.y}px`;
    },
  });
  document.addEventListener('keydown', event => {
    if (reader.isOpen || indexDialog.open || event.target.closest('button,a,input')) return;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); gallery.step(event.key === 'ArrowRight' ? 1 : -1); }
    if (event.key === 'Enter' && event.target.closest('.gallery-stage')) { event.preventDefault(); gallery.open(selectedCard); }
  });
  window.addEventListener('pagehide', gallery.dispose, { once: true });
} catch (error) {
  console.error(error);
  document.querySelector('.gallery-loading').textContent = 'This bookshelf needs WebGL. You can still browse the albums in the collection.';
}
