import './memory-detail.css';

const memoryPhotos = ['italy', 'mountains', 'coast', 'lake', 'forest', 'stars'].map(name => `/memories/${name}.jpg`);

export function createMemoryDetail({ onOpen, onClose }) {
  const dialog = document.createElement('dialog');
  dialog.className = 'memory-detail';
  dialog.setAttribute('aria-labelledby', 'detail-title');
  dialog.innerHTML = `
    <header class="detail-header"><button class="detail-close" aria-label="Close memory and return to collection">× <span>Back to collection</span></button><span>STILLS / THE MEMORY COLLECTION</span></header>
    <div class="detail-layout"><section class="detail-story"><span class="detail-eyebrow">A MEMORY WORTH KEEPING</span><h2 id="detail-title"></h2><p class="detail-copy">Some places stay with us long after we leave.</p><div class="detail-card" aria-label="Selected memory card"><div class="detail-card-brand">Stills</div><span class="detail-card-chip" aria-hidden="true"></span><img alt=""/><div class="detail-card-bottom"><strong></strong><small></small></div></div><span class="detail-sample">A preview with sample photographs</span></section>
    <section class="detail-photos" aria-label="Memory photographs. Swipe to browse."><div class="detail-photo"><img alt="" draggable="false"/></div><div class="detail-photo-bottom"><span>THE MOMENTS THAT STAY</span><div class="detail-dots" aria-label="Choose a photograph"></div></div><div class="detail-thumbnails"></div></section></div>`;
  document.body.appendChild(dialog);
  const closeButton = dialog.querySelector('.detail-close');
  const mainPhoto = dialog.querySelector('.detail-photo img');
  const cardPhoto = dialog.querySelector('.detail-card img');
  let photos = [], current = 0, lastFocus = null, gesture = null;

  function showPhoto(index) {
    current = (index + photos.length) % photos.length;
    mainPhoto.src = photos[current];
    mainPhoto.alt = `Sample memory photograph ${current + 1}`;
    dialog.querySelectorAll('.detail-dots button,.detail-thumbnails button').forEach(button => {
      const active = Number(button.dataset.photo) === current;
      button.setAttribute('aria-current', String(active));
      button.setAttribute('aria-pressed', String(active));
    });
  }
  function close() { if (dialog.open) dialog.close(); }
  closeButton.addEventListener('click', close);
  dialog.addEventListener('close', () => { onClose(); lastFocus?.focus({ preventScroll: true }); });
  dialog.querySelectorAll('.detail-dots,.detail-thumbnails').forEach(group => group.addEventListener('click', event => {
    const button = event.target.closest('[data-photo]');
    if (button) showPhoto(Number(button.dataset.photo));
  }));
  dialog.addEventListener('keydown', event => {
    event.stopPropagation();
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); showPhoto(current + (event.key === 'ArrowRight' ? 1 : -1)); }
  });
  const photoArea = dialog.querySelector('.detail-photos');
  photoArea.addEventListener('pointerdown', event => {
    if (event.button !== 0 || event.target.closest('button')) return;
    gesture = { id: event.pointerId, x: event.clientX, y: event.clientY };
    photoArea.setPointerCapture(event.pointerId);
  });
  photoArea.addEventListener('pointerup', event => {
    if (!gesture || gesture.id !== event.pointerId) return;
    const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
    gesture = null;
    if (photoArea.hasPointerCapture(event.pointerId)) photoArea.releasePointerCapture(event.pointerId);
    if (Math.abs(dx) > 48 && Math.abs(dx) > Math.abs(dy) * 1.2) showPhoto(current + (dx < 0 ? 1 : -1));
  });
  photoArea.addEventListener('pointercancel', () => { gesture = null; });
  dialog.addEventListener('dragstart', event => event.preventDefault());

  return {
    get isOpen() { return dialog.open; },
    open(card) {
      if (dialog.open) return;
      lastFocus = document.activeElement;
      photos = [card.photo, ...memoryPhotos.filter(photo => photo !== card.photo)];
      dialog.style.setProperty('--memory-color', card.color);
      dialog.querySelector('#detail-title').textContent = card.title;
      dialog.querySelector('.detail-card-bottom strong').textContent = card.title;
      dialog.querySelector('.detail-card-bottom small').textContent = card.year;
      cardPhoto.src = card.photo; cardPhoto.alt = '';
      dialog.querySelector('.detail-dots').innerHTML = photos.map((_, index) => `<button data-photo="${index}" aria-label="View photograph ${index + 1}" aria-pressed="false"></button>`).join('');
      dialog.querySelector('.detail-thumbnails').innerHTML = photos.map((photo, index) => `<button data-photo="${index}" aria-label="View photograph ${index + 1}" aria-pressed="false"><img src="${photo}" alt=""/></button>`).join('');
      showPhoto(0); onOpen(); dialog.showModal(); closeButton.focus({ preventScroll: true });
    },
    close,
  };
}
