import './style.css';
import './warm-theme.css';
import './app.css';
import { api, allPhotos, clearTokens, getTokens, saveTokens } from './api.js';
import { createAlbumGallery } from './shelf-gallery.js';
import { createAlbumReader } from './album-reader.js';

const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
const emptyCover = `${import.meta.env.BASE_URL}memories/empty.svg`;
const $ = selector => document.querySelector(selector);
let albums = [], gallery, activeCategory = 'All memories', selected, managed;
let folderLink = '', nextPage = '', files = [], selection = new Map();

$('#app').innerHTML = `
<main class="collection">
  <header class="site-header"><button class="index-trigger" type="button">View all albums</button><div class="brand"><h1>Stills</h1><p>A home for memories</p></div><div class="header-actions"><button class="new-album-trigger" type="button">+ New album</button><button class="logout-trigger" type="button">Sign out</button></div></header>
  <nav class="category-tabs" aria-label="Filter memories">${['All memories','Travel','Everyday','Together'].map((name,i) => `<button type="button" data-category="${name}" aria-pressed="${i===0}">${name}</button>`).join('')}</nav>
  <section class="gallery-stage" aria-label="Memory album bookshelf" tabindex="0"><div id="album-gallery"></div><div class="gallery-loading" role="status">Loading your memories…</div><div class="stage-caption"><span class="interaction-hint">DRAG OR SCROLL TO EXPLORE <span>·</span> CLICK A BOOK TO OPEN</span></div><div class="book-tooltip" aria-hidden="true"><strong></strong><span>OPEN ALBUM ↗</span></div><button class="shelf-arrow shelf-arrow-prev" type="button" aria-label="Previous album">‹</button><button class="shelf-arrow shelf-arrow-next" type="button" aria-label="Next album">›</button><span class="sr-only current-album" aria-live="polite"></span></section>
</main>
<p class="app-message" role="status" aria-live="polite" hidden></p>
<dialog class="album-index" aria-labelledby="index-title"><header><div><span class="eyebrow">YOUR COLLECTION</span><h2 id="index-title">Every memory.</h2></div><button class="close-index" type="button" aria-label="Close album collection">×</button></header><label class="search-box"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/></svg><input type="search" placeholder="Find a memory…" aria-label="Search memory albums"/></label><div class="index-grid"></div><p class="no-results" hidden>No albums found.</p></dialog>
<dialog class="app-dialog auth-dialog" aria-labelledby="auth-title"><span class="eyebrow">WELCOME TO STILLS</span><h2 id="auth-title">Your memories await.</h2><p>Sign in to keep your albums together.</p><form id="auth-form"><label>Username<input name="username" autocomplete="username" required/></label><label class="register-only" hidden>Email<input name="email" type="email" autocomplete="email"/></label><label>Password<input name="password" type="password" autocomplete="current-password" required/></label><p class="form-error" role="alert" hidden></p><button class="primary-button" type="submit">Sign in</button></form><button class="text-button auth-switch" type="button">Create an account</button></dialog>
<dialog class="app-dialog create-dialog" aria-labelledby="create-title"><div class="dialog-heading"><div><span class="eyebrow">A NEW COLLECTION</span><h2 id="create-title">Create an album.</h2></div><button class="dialog-close" type="button" aria-label="Close">×</button></div><form id="create-form"><label>Album title<input name="title" maxlength="255" placeholder="A weekend in the hills" required/></label><label>Description<textarea name="description" rows="3" placeholder="A few words about these days"></textarea></label><div class="form-row"><label>Category<select name="category"><option>Travel</option><option>Everyday</option><option>Together</option></select></label><label>Cover color<input name="color" type="color" value="#677a71"/></label></div><p class="form-error" role="alert" hidden></p><button class="primary-button" type="submit">Create album</button></form></dialog>
<dialog class="app-dialog manage-dialog" aria-labelledby="manage-title"><div class="dialog-heading"><div><span class="eyebrow">FILL THE PAGES</span><h2 id="manage-title"></h2></div><button class="dialog-close" type="button" aria-label="Close">×</button></div><div class="manage-content"><section><h3>Upload from your device</h3><p>JPG, PNG, or WebP · up to 300 MB each</p><form id="upload-form"><input name="photos" type="file" accept="image/jpeg,image/png,image/webp" multiple required/><label>Caption for these photos<input name="caption" maxlength="255" placeholder="Optional"/></label><button class="primary-button" type="submit">Upload photos</button></form></section><section class="drive-section"><h3>Import from a shared Google Drive folder</h3><p>Connect a Google account that can open the folder, then paste its link. Photos can be up to 300 MB each.</p><div class="drive-connection"></div><form id="folder-form"><label>Shared folder link<input name="folder_link" type="url" placeholder="https://drive.google.com/drive/folders/…" required/></label><button type="submit">Show photos</button></form><div class="drive-results"></div><div class="drive-controls"><button class="next-drive-page" type="button" hidden>Next page</button><button class="primary-button import-drive" type="button" disabled>Import selected photos</button></div></section></div><section class="manage-photos"><h3>Photos in this album</h3><div class="managed-photo-list" aria-live="polite">Loading photos…</div></section><div class="manage-footer"><p class="manage-status" role="status" aria-live="polite"></p><button class="delete-album" type="button">Delete album</button></div></dialog>`;

const indexDialog = $('.album-index'), authDialog = $('.auth-dialog'), createDialog = $('.create-dialog'), manageDialog = $('.manage-dialog');
const reader = createAlbumReader({
  onOpen: () => gallery?.setActive(false),
  onClose: () => gallery?.setActive(true),
  onManage: openManager,
  onDeletePhoto: removePhoto,
  onDeleteAlbum: removeAlbum,
  onError: error => notice(error.message, true),
});
function notice(text, error=false) { const node=$('.app-message'); node.textContent=text; node.hidden=false; node.classList.toggle('error',error); clearTimeout(notice.timer); notice.timer=setTimeout(() => node.hidden=true,6000); }
function showError(form, text) { const node=form.querySelector('.form-error'); node.textContent=text; node.hidden=!text; }
function toCard(album) { return {...album,year:String(new Date(album.created_at).getFullYear()),photo:album.cover_url||emptyCover}; }
function thumbnail(file) { try { const url=new URL(file.thumbnailLink); return url.protocol==='https:' ? `<img src="${esc(url.href)}" alt="" loading="lazy" referrerpolicy="no-referrer"/>` : ''; } catch { return ''; } }
function visibleAlbums() { return albums.filter(a => activeCategory==='All memories'||a.category===activeCategory); }
function renderShelf() {
  gallery?.dispose(); gallery=null; selected=null; $('#album-gallery').replaceChildren(); $('.collection').classList.remove('ready');
  const list=visibleAlbums(), empty=$('.gallery-loading');
  $('.shelf-arrow-prev').hidden=$('.shelf-arrow-next').hidden=list.length<2;
  empty.textContent=list.length?'Gathering your memories…':albums.length?'No albums in this category yet.':'Your bookshelf is empty. Create your first album.';
  if (!list.length) return;
  try {
    gallery=createAlbumGallery($('#album-gallery'),list,{
      onReady:() => {empty.textContent='';$('.collection').classList.add('ready');},
      onSelect:openCard,
      onChange:card => {selected=card;$('.current-album').textContent=card.title;},
      onHover:(card,pos) => {const tip=$('.book-tooltip');tip.classList.toggle('is-visible',!!card);if(!card)return;tip.querySelector('strong').textContent=card.title;tip.style.left=`${Math.max(100,Math.min($('.gallery-stage').clientWidth-100,pos.x))}px`;tip.style.top=`${pos.y}px`;}
    });
  } catch(error) {console.error(error);empty.textContent='Your browser cannot show the 3D shelf. Use View all albums to browse.';}
}
async function loadAlbums() { albums=(await api('/albums/')).map(toCard);renderShelf();if(reader.isOpen)gallery?.setActive(false);renderIndex(); }
async function removeAlbum(card) {
  await api(`/albums/${card.id}/`, {method:'DELETE'});
  await loadAlbums();
  notice('Album deleted from your collection.');
}
async function removePhoto(card, photoId) {
  await api(`/albums/${card.id}/photos/${photoId}/`, {method:'DELETE'});
  const photos = await allPhotos(card.id);
  await loadAlbums();
  const updated = albums.find(album => album.id === card.id);
  notice('Photo deleted from this album.');
  return {...updated, photos, photo: photos[0]?.url || updated.photo};
}
async function openCard(card) {
  if (!card) return;
  try {const photos=await allPhotos(card.id);if(indexDialog.open)indexDialog.close();reader.open({...card,photos,photo:photos[0]?.url||card.photo});}
  catch(error){notice(error.message,true);}
}
function renderIndex() {
  const query=indexDialog.querySelector('input').value.trim().toLowerCase();
  const matches=albums.filter(a => `${a.title} ${a.description} ${a.year} ${a.category}`.toLowerCase().includes(query));
  $('.index-grid').innerHTML=matches.map(a => `<div class="index-card-wrap"><button class="index-card" data-card="${esc(a.id)}" type="button"><span class="index-card-face" style="--card:${esc(a.color)}"><span class="index-mark">Stills</span><img src="${esc(a.photo)}" alt=""/><span class="index-card-title">${esc(a.title)}</span><span class="index-year">${esc(a.year)}</span></span><strong>${esc(a.title)}</strong><small>${esc(a.category)} · ${a.photo_count??0} photos</small></button><div class="index-card-actions"><button class="manage-card" data-manage="${esc(a.id)}" type="button">Manage album ↗</button><button class="index-delete-album" data-delete-album="${esc(a.id)}" type="button">Delete album</button></div></div>`).join('');
  $('.no-results').hidden=matches.length>0;
}
function openManager(card) {
  if (!card)return;
  if (indexDialog.open) indexDialog.close();
  managed=card;selection.clear();folderLink='';nextPage='';
  $('#manage-title').textContent=card.title;$('#folder-form').reset();$('#upload-form').reset();
  $('.drive-results').replaceChildren();$('.manage-status').textContent='';$('.next-drive-page').hidden=true;$('.import-drive').disabled=true;
  manageDialog.showModal();refreshConnection();loadManagedPhotos();
}
async function loadManagedPhotos() {
  const albumId = managed?.id;
  const list = $('.managed-photo-list');
  list.textContent = 'Loading photos…';
  try {
    const photos = await allPhotos(albumId);
    if (managed?.id !== albumId || !manageDialog.open) return;
    list.innerHTML = photos.length ? photos.map(photo => `<div class="managed-photo"><img src="${esc(photo.url)}" alt="" loading="lazy"/><span>${esc(photo.caption || photo.filename || 'Untitled photo')}</span><button type="button" data-delete-photo="${esc(photo.id)}" aria-label="Delete ${esc(photo.filename || 'photo')}">Delete</button></div>`).join('') : '<p>No photos in this album yet.</p>';
  } catch(error) { if (managed?.id === albumId) list.textContent = error.message; }
}
async function refreshConnection() {
  try {const {connected}=await api('/integrations/google/connection/');$('.drive-connection').innerHTML=connected?'<span>Google Drive connected</span><button type="button" class="disconnect-drive">Disconnect</button>':'<button type="button" class="connect-drive">Connect Google Drive</button>';}
  catch(error){$('.drive-connection').textContent=error.message;}
}
async function listFolder(token='') {
  const result=await api(`/integrations/google/folder-photos/?folder_link=${encodeURIComponent(folderLink)}&album_id=${encodeURIComponent(managed.id)}${token?`&page_token=${encodeURIComponent(token)}`:''}`);
  files=result.files;nextPage=result.next_page_token||'';$('.next-drive-page').hidden=!nextPage;
  $('.drive-results').innerHTML=`<h4>${esc(result.folder.name)}</h4><p>${selection.size} selected · up to 10 per import</p>${files.length?files.map(file => `<label class="drive-file"><input type="checkbox" data-file="${esc(file.id)}" ${selection.has(file.id)?'checked':''} ${file.already_imported||file.capabilities?.canDownload===false?'disabled':''}/>${thumbnail(file)}<span>${esc(file.name)}</span><small>${file.size?`${(Number(file.size)/1048576).toFixed(1)} MB`:''}${file.already_imported?' · In album':''}</small></label>`).join(''):'<p>No supported photos on this page.</p>'}`;
  $('.import-drive').disabled=selection.size===0;
}

$('.index-trigger').addEventListener('click',()=>{renderIndex();gallery?.setActive(false);indexDialog.showModal();});
$('.close-index').addEventListener('click',()=>indexDialog.close());
indexDialog.addEventListener('close',()=>{if(!reader.isOpen)gallery?.setActive(true);});
indexDialog.querySelector('input').addEventListener('input',renderIndex);
indexDialog.addEventListener('click',async e=>{const remove=e.target.closest('[data-delete-album]');if(remove){const card=albums.find(a=>a.id===remove.dataset.deleteAlbum);if(!card||!confirm(`Delete “${card.title}” from your collection? Its records and stored photos will be retained.`))return;remove.disabled=true;try{await removeAlbum(card);}catch(error){notice(error.message,true);remove.disabled=false;}return;}const manage=e.target.closest('[data-manage]');if(manage){openManager(albums.find(a=>a.id===manage.dataset.manage));return;}const card=e.target.closest('[data-card]');if(card)openCard(albums.find(a=>a.id===card.dataset.card));});
$('.shelf-arrow-prev').addEventListener('click',()=>gallery?.step(-1));
$('.shelf-arrow-next').addEventListener('click',()=>gallery?.step(1));
document.querySelectorAll('[data-category]').forEach(button=>button.addEventListener('click',()=>{activeCategory=button.dataset.category;document.querySelectorAll('[data-category]').forEach(tab=>tab.setAttribute('aria-pressed',String(tab===button)));renderShelf();}));
document.addEventListener('keydown',e=>{if(reader.isOpen||indexDialog.open||authDialog.open||createDialog.open||manageDialog.open||e.target.closest('button,a,input,select,textarea'))return;if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();gallery?.step(e.key==='ArrowRight'?1:-1);}if(e.key==='Enter'&&e.target.closest('.gallery-stage')){e.preventDefault();openCard(selected);}});

let registering=false;
function showAuth(){if(!authDialog.open)authDialog.showModal();}
authDialog.addEventListener('cancel',e=>e.preventDefault());
$('.auth-switch').addEventListener('click',()=>{registering=!registering;$('#auth-title').textContent=registering?'Begin your collection.':'Your memories await.';$('.register-only').hidden=!registering;$('#auth-form [name=email]').required=registering;$('#auth-form [name=password]').autocomplete=registering?'new-password':'current-password';$('#auth-form .primary-button').textContent=registering?'Create account':'Sign in';$('.auth-switch').textContent=registering?'I already have an account':'Create an account';showError($('#auth-form'),'');});
$('#auth-form').addEventListener('submit',async e=>{e.preventDefault();const form=e.currentTarget,button=form.querySelector('[type=submit]'),values=Object.fromEntries(new FormData(form));button.disabled=true;try{clearTokens();if(registering)await api('/auth/register/',{method:'POST',body:JSON.stringify(values)});saveTokens(await api('/auth/login/',{method:'POST',body:JSON.stringify({username:values.username,password:values.password})}));await loadAlbums();authDialog.close();showError(form,'');}catch(error){showError(form,error.message);}finally{button.disabled=false;}});
$('.logout-trigger').addEventListener('click',()=>{clearTokens();albums=[];renderShelf();showAuth();});

$('.new-album-trigger').addEventListener('click',()=>createDialog.showModal());
createDialog.querySelector('.dialog-close').addEventListener('click',()=>createDialog.close());
$('#create-form').addEventListener('submit',async e=>{e.preventDefault();const form=e.currentTarget,button=form.querySelector('[type=submit]');button.disabled=true;try{const created=await api('/albums/',{method:'POST',body:JSON.stringify(Object.fromEntries(new FormData(form)))});form.reset();showError(form,'');createDialog.close();await loadAlbums();openManager(albums.find(a=>a.id===created.id));notice('Album created. Add your first photos.');}catch(error){showError(form,error.message);}finally{button.disabled=false;}});

manageDialog.querySelector('.dialog-close').addEventListener('click',()=>manageDialog.close());
$('#upload-form').addEventListener('submit',async e=>{e.preventDefault();const form=e.currentTarget,button=form.querySelector('[type=submit]');button.disabled=true;try{const result=await api(`/albums/${managed.id}/photos/bulk-upload/`,{method:'POST',body:new FormData(form)});$('.manage-status').textContent=`${result.uploaded} photos uploaded${result.skipped?`, ${result.skipped} skipped`:''}.`;form.reset();await loadAlbums();managed=albums.find(a=>a.id===managed.id);await loadManagedPhotos();}catch(error){$('.manage-status').textContent=error.message;}finally{button.disabled=false;}});
$('.drive-connection').addEventListener('click',async e=>{try{if(e.target.closest('.connect-drive')){const result=await api('/integrations/google/connect/',{method:'POST',body:JSON.stringify({return_origin:location.origin})});location.assign(result.authorization_url);}else if(e.target.closest('.disconnect-drive')){await api('/integrations/google/connection/',{method:'DELETE'});refreshConnection();}}catch(error){$('.manage-status').textContent=error.message;}});
$('#folder-form').addEventListener('submit',async e=>{e.preventDefault();folderLink=new FormData(e.currentTarget).get('folder_link').trim();selection.clear();try{await listFolder();}catch(error){$('.manage-status').textContent=error.message;}});
$('.next-drive-page').addEventListener('click',async()=>{try{await listFolder(nextPage);}catch(error){$('.manage-status').textContent=error.message;}});
$('.drive-results').addEventListener('change',e=>{const box=e.target.closest('[data-file]');if(!box)return;const file=files.find(f=>f.id===box.dataset.file);if(box.checked){if(selection.size>=10){box.checked=false;$('.manage-status').textContent='Import up to 10 photos at a time.';return;}selection.set(file.id,file);}else selection.delete(file.id);$('.drive-results h4 + p').textContent=`${selection.size} selected · up to 10 per import`;$('.import-drive').disabled=selection.size===0;});
$('.import-drive').addEventListener('click',async e=>{const button=e.currentTarget;button.disabled=true;try{const result=await api(`/albums/${managed.id}/photos/import-drive/`,{method:'POST',body:JSON.stringify({folder_link:folderLink,photos:[...selection.values()].map(f=>({file_id:f.id,resource_key:f.resourceKey||''}))})});$('.manage-status').textContent=`${result.imported} photos imported into ${managed.title}${result.skipped?`; ${result.skipped} already in this album`:''}.`;selection.clear();await listFolder();await loadAlbums();managed=albums.find(a=>a.id===managed.id);await loadManagedPhotos();}catch(error){$('.manage-status').textContent=error.message;}finally{button.disabled=selection.size===0;}});
$('.managed-photo-list').addEventListener('click',async e=>{const button=e.target.closest('[data-delete-photo]');if(!button||!managed)return;if(!confirm('Delete this photo from the album? Its record and stored file will be retained.'))return;button.disabled=true;try{await api(`/albums/${managed.id}/photos/${button.dataset.deletePhoto}/`,{method:'DELETE'});await loadAlbums();managed=albums.find(a=>a.id===managed.id);await loadManagedPhotos();$('.manage-status').textContent='Photo deleted from this album.';if(folderLink)await listFolder();}catch(error){$('.manage-status').textContent=error.message;button.disabled=false;}});
$('.delete-album').addEventListener('click',async e=>{if(!managed||!confirm(`Delete “${managed.title}” from your collection? Its records and stored photos will be retained.`))return;const button=e.currentTarget;button.disabled=true;try{await removeAlbum(managed);manageDialog.close();managed=null;}catch(error){$('.manage-status').textContent=error.message;}finally{button.disabled=false;}});

window.addEventListener('pagehide',()=>gallery?.dispose(),{once:true});
const googleResult = new URLSearchParams(location.search);
if (googleResult.get('google') === 'connected') {
  notice('Google Drive connected. Open an album to import photos.');
  history.replaceState({}, '', location.pathname);
} else if (googleResult.get('google') === 'error') {
  const messages = {
    browser: 'Google Drive connection expired or used a different browser host. Reopen Stills at its configured URL and try again.',
    expired: 'Google Drive connection expired. Start a new connection.',
    denied: 'Google Drive access was not approved. Start a new connection.',
    exchange: 'Google Drive authorization could not be completed. Check OAuth settings and try again.',
    permission: 'Google Drive permission was not granted. Start a new connection.',
  };
  notice(messages[googleResult.get('reason')] || 'Google Drive connection failed. Try again.', true);
  history.replaceState({}, '', location.pathname);
}
if(getTokens())api('/auth/user/').then(loadAlbums).catch(()=>{clearTokens();showAuth();});else showAuth();
