import './album-reader.css';

const chevron = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="m14 6-6 6 6 6"/></svg>';
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);

function makePages(album) {
  const pages = [{ type: 'title', photo: album.photo },
    ...(album.photos || []).map(photo => ({ type: 'photo', id: photo.id, photo: photo.url, caption: photo.caption || '', label: photo.filename }))];
  if (pages.length % 2) pages.push({ type: 'end' });
  return pages.map((page, index) => ({ ...page, index }));
}

export function createAlbumReader({ onOpen, onClose, onManage, onDeletePhoto, onDeleteAlbum, onError }) {
  const dialog = document.createElement('dialog');
  dialog.className = 'album-reader';
  dialog.tabIndex = -1;
  dialog.setAttribute('aria-labelledby', 'reader-title');
  dialog.innerHTML = `
    <header class="reader-header"><button class="reader-back" aria-label="Close album and return to the collection">${chevron}<span>Back to collection</span></button><div class="reader-heading"><span class="reader-eyebrow">A COLLECTION OF MOMENTS</span><h1 id="reader-title"></h1></div><div class="reader-actions"><button class="reader-manage" type="button">Add photos</button><button class="reader-delete-album" type="button">Delete album</button></div></header>
    <section class="reading-stage" aria-label="Open photo album. Swipe left for the next pages and right for the previous pages.">
      <div class="album-book">
        <div class="book-board"></div><div class="paper-stack"></div>
        <div class="album-page page-left"></div><div class="album-page page-right"></div>
        <div class="binding" aria-hidden="true"></div><div class="turn-layer" aria-hidden="true"></div>
        <div class="opening-cover" aria-hidden="true"><div class="cover-outside"></div><div class="cover-inside"></div></div>
      </div>
    </section>
    <footer class="reader-footer"><span class="reader-gesture"><svg viewBox="0 0 28 20" fill="none" stroke="currentColor"><path d="M3 10h22m-5-5 5 5-5 5M8 5l-5 5 5 5"/></svg>Swipe to turn the page</span><div class="reader-pagination"><button class="previous-page" aria-label="Previous pages">${chevron}</button><div class="page-location"><span class="page-counter" role="status" aria-live="polite"></span><div class="reading-progress"><span></span></div></div><button class="next-page" aria-label="Next pages">${chevron}</button></div><span class="sample-note"></span></footer>`;
  document.body.appendChild(dialog);
  const book = dialog.querySelector('.album-book');
  const left = dialog.querySelector('.page-left');
  const right = dialog.querySelector('.page-right');
  const layer = dialog.querySelector('.turn-layer');
  const previousButton = dialog.querySelector('.previous-page');
  const nextButton = dialog.querySelector('.next-page');
  const cover = dialog.querySelector('.opening-cover');
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let album, pages, spread = 0, phase = 'closed', direction = 0, progress = 0;
  let gesture = null, animation = null, openingTimer = null, lastFocus = null;
  let totalSpreads = 1;

  function pageHTML(page) {
    const number = String(page.index + 1).padStart(2, '0');
    const image = (src, alt = 'A memory in this album') => `<img src="${escapeHTML(src)}" alt="${escapeHTML(alt)}" draggable="false" />`;
    let content;
    if (page.type === 'title') {
      content = `<div class="title-page"><span class="page-eyebrow">${escapeHTML(album.year)} &nbsp; / &nbsp; OUR MEMORIES</span><h2>${escapeHTML(album.title)}</h2><div class="title-photo">${image(album.photo, album.title)}</div><p>Some days deserve to stay.</p><span class="title-ornament">✦</span></div>`;
    } else if (page.type === 'end') {
      content = `<div class="title-page"><span class="page-eyebrow">STILLS / MEMORIES</span><h2>${album.photos.length ? 'More moments to come.' : 'Your album is ready.'}</h2><p>${album.photos.length ? 'Add another memory whenever you like.' : 'Use Add photos to fill these pages.'}</p><span class="title-ornament">✦</span></div>`;
    } else if (page.type === 'pair') {
      content = `<div class="pair-page"><span class="page-eyebrow">THE LITTLE THINGS</span><div class="photo-pair"><figure>${image(page.photo)}</figure><figure>${image(page.secondPhoto)}</figure></div><p class="photo-caption">${page.caption}</p></div>`;
    } else if (page.type === 'full') {
      content = `<div class="full-photo">${image(page.photo)}<span>${page.label}</span></div>`;
    } else {
      content = `<div class="photo-page"><span class="page-eyebrow">${escapeHTML(page.label)}</span><figure class="mounted-photo">${image(page.photo, page.caption || page.label)}</figure><p class="photo-caption">${escapeHTML(page.caption)}</p><span class="photo-date">${escapeHTML(album.year)} &nbsp; — &nbsp; A MOMENT KEPT</span><button class="reader-delete-photo" type="button" data-delete-photo="${escapeHTML(page.id)}">Delete photo</button></div>`;
    }
    return `${content}<div class="printed-folio"><span>STILLS / ${escapeHTML(album.year)}</span><span>${number}</span></div>`;
  }

  function renderSpread() {
    left.innerHTML = pageHTML(pages[spread * 2]);
    right.innerHTML = pageHTML(pages[spread * 2 + 1]);
    layer.replaceChildren(); direction = 0; progress = 0;
    book.removeAttribute('data-turn');
    updateControls();
  }

  function updateControls() {
    const focusedControl = document.activeElement;
    previousButton.disabled = spread === 0 || phase !== 'idle';
    nextButton.disabled = spread === totalSpreads - 1 || phase !== 'idle';
    if ((focusedControl === previousButton || focusedControl === nextButton) && focusedControl.disabled && dialog.open) {
      dialog.focus({ preventScroll: true });
    }
    const start = String(spread * 2 + 1).padStart(2, '0');
    const end = String(spread * 2 + 2).padStart(2, '0');
    dialog.querySelector('.page-counter').textContent = `${start} — ${end} / ${pages.length}`;
    dialog.querySelector('.reading-progress > span').style.width = `${(spread + 1) / totalSpreads * 100}%`;
    dialog.dataset.spread = String(spread + 1);
    dialog.dataset.phase = phase;
    dialog.querySelector('.reading-stage').setAttribute('aria-busy', String(phase === 'turning' || phase === 'dragging'));
  }

  function canTurn(dir) { return spread + dir >= 0 && spread + dir < totalSpreads; }
  function prepareTurn(dir) {
    if (!canTurn(dir)) return false;
    direction = dir; progress = 0;
    book.dataset.turn = dir > 0 ? 'next' : 'previous';
    // The underside of a sheet is the first page of the next spread (or the last of the previous).
    const frontPage = pages[spread * 2 + (dir > 0 ? 1 : 0)];
    const backPage = pages[dir > 0 ? spread * 2 + 2 : spread * 2 - 1];
    if (dir > 0) right.innerHTML = pageHTML(pages[spread * 2 + 3]);
    else left.innerHTML = pageHTML(pages[spread * 2 - 2]);
    layer.innerHTML = `<div class="turning-sheet ${dir > 0 ? 'turn-next' : 'turn-previous'}"><div class="sheet-face sheet-front">${pageHTML(frontPage)}</div><div class="sheet-face sheet-back">${pageHTML(backPage)}</div></div>`;
    return true;
  }

  function drawTurn(value) {
    progress = Math.max(0, Math.min(1, value));
    const sheet = layer.firstElementChild;
    if (sheet) sheet.style.transform = `rotateY(${-direction * progress * 180}deg)`;
  }

  async function settleTurn(commit) {
    const sheet = layer.firstElementChild;
    if (!sheet) { phase = 'idle'; updateControls(); return; }
    phase = 'turning'; updateControls();
    const finish = commit ? 1 : 0;
    animation = sheet.animate([
      { transform: `rotateY(${-direction * progress * 180}deg)` },
      { transform: `rotateY(${-direction * finish * 180}deg)` },
    ], { duration: reducedMotion ? 0 : Math.max(180, Math.abs(finish - progress) * 680), easing: 'cubic-bezier(.22,.7,.25,1)', fill: 'forwards' });
    try { await animation.finished; } catch { return; }
    if (!dialog.open) return;
    if (commit) spread += direction;
    animation.cancel(); animation = null;
    phase = 'idle'; renderSpread();
  }

  function turn(dir) {
    if (phase !== 'idle' || !canTurn(dir)) return;
    prepareTurn(dir); settleTurn(true);
  }

  function close() { if (dialog.open) dialog.close(); }
  dialog.querySelector('.reader-back').addEventListener('click', close);
  dialog.querySelector('.reader-manage').addEventListener('click', () => { close(); onManage(album); });
  dialog.querySelector('.reader-delete-album').addEventListener('click', async event => {
    if (!album || !confirm(`Delete “${album.title}” from your collection? Its records and stored photos will be retained.`)) return;
    const button = event.currentTarget;
    button.disabled = true;
    try { await onDeleteAlbum(album); close(); }
    catch (error) { onError(error); }
    finally { button.disabled = false; }
  });
  dialog.addEventListener('click', async event => {
    const button = event.target.closest('[data-delete-photo]');
    if (!button || phase !== 'idle') return;
    event.stopPropagation();
    if (!confirm('Delete this photo from the album? Its record and stored file will be retained.')) return;
    button.disabled = true;
    try {
      const updatedAlbum = await onDeletePhoto(album, button.dataset.deletePhoto);
      if (!dialog.open) return;
      album = updatedAlbum;
      pages = makePages(album);
      totalSpreads = pages.length / 2;
      spread = Math.min(spread, totalSpreads - 1);
      dialog.querySelector('.sample-note').textContent = `${album.photos.length} ${album.photos.length === 1 ? 'photo' : 'photos'} · ${pages.length} pages`;
      renderSpread();
    } catch (error) { onError(error); button.disabled = false; }
  });
  previousButton.addEventListener('click', () => turn(-1));
  nextButton.addEventListener('click', () => turn(1));
  dialog.addEventListener('close', () => {
    phase = 'closed'; clearTimeout(openingTimer); animation?.cancel(); animation = null;
    if (gesture && dialog.hasPointerCapture(gesture.id)) dialog.releasePointerCapture(gesture.id);
    gesture = null; layer.replaceChildren(); book.classList.remove('is-opening');
    onClose(); lastFocus?.focus({ preventScroll: true });
  });
  dialog.addEventListener('keydown', event => {
    event.stopPropagation();
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
      event.preventDefault(); turn(event.key === 'ArrowLeft' ? -1 : 1);
    }
    if (event.key === 'Home' && phase === 'idle') { event.preventDefault(); spread = 0; renderSpread(); }
    if (event.key === 'End' && phase === 'idle') { event.preventDefault(); spread = totalSpreads - 1; renderSpread(); }
  });
  dialog.addEventListener('pointerdown', event => {
    if (event.button !== 0 || phase !== 'idle' || gesture || event.target.closest('button')) return;
    gesture = { id: event.pointerId, x: event.clientX, y: event.clientY, dx: 0 };
    dialog.setPointerCapture(event.pointerId);
  });
  dialog.addEventListener('pointermove', event => {
    if (!gesture || gesture.id !== event.pointerId) return;
    const dx = event.clientX - gesture.x, dy = event.clientY - gesture.y;
    gesture.dx = dx;
    if (phase === 'idle') {
      if (Math.abs(dx) < 12 || Math.abs(dx) < Math.abs(dy) * 1.15) return;
      const dir = dx < 0 ? 1 : -1;
      if (!prepareTurn(dir)) return;
      phase = 'dragging'; updateControls();
    }
    if (phase === 'dragging') drawTurn(Math.max(0, -direction * dx) / Math.max(160, book.clientWidth * .52));
  });
  function releaseGesture(event, cancelled = false) {
    if (!gesture || gesture.id !== event.pointerId) return;
    const dx = gesture.dx; gesture = null;
    if (dialog.hasPointerCapture(event.pointerId)) dialog.releasePointerCapture(event.pointerId);
    if (phase === 'dragging') settleTurn(!cancelled && -direction * dx > Math.min(72, book.clientWidth * .12));
  }
  dialog.addEventListener('pointerup', event => releaseGesture(event));
  dialog.addEventListener('pointercancel', event => releaseGesture(event, true));
  dialog.addEventListener('lostpointercapture', event => { if (gesture) releaseGesture(event, true); });
  dialog.addEventListener('dragstart', event => event.preventDefault());

  return {
    get isOpen() { return dialog.open; },
    open(selectedAlbum) {
      if (dialog.open) return;
      album = selectedAlbum; pages = makePages(album); totalSpreads = pages.length / 2; spread = 0; phase = 'opening';
      lastFocus = document.activeElement;
      dialog.style.setProperty('--album-color', album.color);
      dialog.querySelector('#reader-title').textContent = album.title;
      dialog.querySelector('.sample-note').textContent = `${album.photos.length} ${album.photos.length === 1 ? 'photo' : 'photos'} · ${pages.length} pages`;
      dialog.querySelector('.cover-outside').innerHTML = `<span class="cover-overline">A COLLECTION OF MOMENTS</span><h2>${escapeHTML(album.title)}</h2><img src="${escapeHTML(album.photo)}" alt="" draggable="false"/><span class="cover-year">${escapeHTML(album.year)}</span>`;
      renderSpread(); onOpen(); dialog.showModal();
      cover.hidden = false; book.classList.add('is-opening');
      openingTimer = setTimeout(() => {
        if (!dialog.open) return;
        cover.hidden = true; book.classList.remove('is-opening'); phase = 'idle'; updateControls();
      }, reducedMotion ? 0 : 1150);
      // Warm the photo cache before later pages are turned.
      [...new Set(pages.flatMap(page => [page.photo, page.secondPhoto]))].forEach(src => { const image = new Image(); image.src = src; });
    },
    close,
  };
}

