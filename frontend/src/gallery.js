import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

export function createAlbumGallery(container, albums, options) {
  const scene = new THREE.Scene();
  // An elevated orthographic view keeps the tightly spaced ribbon consistent in size.
  const camera = new THREE.OrthographicCamera(-10, 10, 3.3, -3.3, .1, 80);
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);
  const canvas = renderer.domElement;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  scene.add(new THREE.HemisphereLight(0xfaf0dc, 0x45515c, 2.1));
  const light = new THREE.DirectionalLight(0xffedd1, 3);
  light.position.set(-3, 7, 8); light.castShadow = true; light.shadow.mapSize.set(1024, 1024);
  Object.assign(light.shadow.camera, { left: -12, right: 12, top: 7, bottom: -7 });
  light.shadow.normalBias = .04; scene.add(light);
  const rim = new THREE.DirectionalLight(0xc5d3ff, 1.7); rim.position.set(7, 4, -3); scene.add(rim);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(70, 50), new THREE.ShadowMaterial({ opacity: .36 }));
  floor.rotation.x = -Math.PI / 2; floor.position.y = -1.56; floor.receiveShadow = true; scene.add(floor);
  const textures = [], models = [];
  let disposed = false, active = true, list = albums, current = 0, target = 0, announced = -1, hovered = null;
  let drag = null, snapTimer;
  let motionEnabled = !reducedMotion, motionTime = 0, waveCenter = -5, sweepSpan = 6;
  let resumeWaveAt = 0;
  const wrap = (index, length = list.length) => ((index % length) + length) % length;
  const linenColor = album => `#${album.color.slice(1).match(/../g).map(channel => Math.round(parseInt(channel, 16) * .8).toString(16).padStart(2, '0')).join('')}`;
  function mesh(w, h, d, material, group, x = 0, z = 0, radius = .035) {
    const item = new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 2, radius), material);
    item.position.set(x, 0, z); item.castShadow = true; item.receiveShadow = true; group.add(item); return item;
  }
  function coverTexture(album) {
    const surface = document.createElement('canvas'); surface.width = 1200; surface.height = 760;
    const ctx = surface.getContext('2d');
    const texture = new THREE.CanvasTexture(surface); texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy(); textures.push(texture);
    function paint(photo) {
      ctx.fillStyle = linenColor(album); ctx.fillRect(0, 0, 1200, 760);
      const wash = ctx.createLinearGradient(0, 0, 1200, 760);
      wash.addColorStop(0, '#ffffff34'); wash.addColorStop(.46, '#ffffff00'); wash.addColorStop(1, '#00000037');
      ctx.fillStyle = wash; ctx.fillRect(0, 0, 1200, 760);
      ctx.fillStyle = '#ffffff14'; ctx.beginPath(); ctx.arc(1030, -50, 430, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = '#ffffff19'; ctx.lineWidth = 2;
      for (let radius = 330; radius < 620; radius += 62) { ctx.beginPath(); ctx.arc(995, 43, radius, .35, 2.18); ctx.stroke(); }
      ctx.fillStyle = '#fff8ea'; ctx.textAlign = 'left';
      ctx.font = '52px Georgia'; ctx.fillText('stills.', 78, 105);
      ctx.font = '20px Arial'; ctx.letterSpacing = '3px'; ctx.fillText('M E M O R Y   C A R D', 78, 151);
      ctx.letterSpacing = '0px';
      // A small metallic inlay and contactless mark make the object read as a card.
      const chip = ctx.createLinearGradient(85, 260, 245, 370);
      chip.addColorStop(0, '#fff0bf'); chip.addColorStop(.48, '#b9995f'); chip.addColorStop(1, '#eadbb0');
      ctx.fillStyle = chip; ctx.beginPath(); ctx.roundRect(83, 272, 151, 108, 15); ctx.fill();
      ctx.strokeStyle = '#685d46'; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.roundRect(83, 272, 151, 108, 15); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(158, 274); ctx.lineTo(158, 378); ctx.moveTo(85, 326); ctx.lineTo(232, 326); ctx.stroke();
      ctx.strokeStyle = '#fff8eac9'; ctx.lineWidth = 5;
      for (let radius = 16; radius <= 43; radius += 13) { ctx.beginPath(); ctx.arc(275, 326, radius, -.8, .8); ctx.stroke(); }
      ctx.fillStyle = '#f7e5c3'; ctx.fillRect(321, 173, 352, 346);
      if (photo) {
        const width = 332, height = 326, scale = Math.max(width / photo.width, height / photo.height);
        const sw = width / scale, sh = height / scale;
        ctx.drawImage(photo, (photo.width - sw) / 2, (photo.height - sh) / 2, sw, sh, 331, 183, width, height);
      }
      ctx.fillStyle = '#fff8ea'; ctx.textAlign = 'left'; ctx.font = '56px Georgia';
      const words = album.title.split(' '), lines = []; let line = '';
      for (const word of words) { const next = `${line} ${word}`.trim(); if (ctx.measureText(next).width > 520 && line) { lines.push(line); line = word; } else line = next; } lines.push(line);
      lines.slice(0, 2).forEach((text, i) => ctx.fillText(text, 83, 535 + i * 68, 530));
      ctx.fillStyle = '#f7e8d1'; ctx.font = '25px Arial'; ctx.letterSpacing = '4px'; ctx.fillText(album.year, 85, 696);
      ctx.letterSpacing = '0px'; texture.needsUpdate = true;
    }
    paint();
    const ready = new Promise(resolve => { const photo = new Image(); photo.onload = () => { if (!disposed) paint(photo); resolve(); }; photo.onerror = resolve; photo.src = album.photo; });
    return { texture, ready };
  }
  const loads = albums.map(album => {
    const model = new THREE.Group(); model.userData.album = album; scene.add(model); models.push(model);
    const cardMaterial = new THREE.MeshStandardMaterial({ color: linenColor(album), metalness: .12, roughness: .46 });
    mesh(4.42, 2.8, .075, cardMaterial, model, 0, 0, .036);
    const { texture, ready } = coverTexture(album);
    const front = new THREE.Mesh(new THREE.PlaneGeometry(4.29, 2.67), new THREE.MeshBasicMaterial({ map: texture, toneMapped: false, side: THREE.DoubleSide }));
    front.position.z = .04; model.add(front);
    model.userData.lift = 0;
    model.traverse(child => { if (child.isMesh) child.userData.albumModel = model; }); return ready;
  });
  Promise.all(loads).then(() => { if (!disposed) options.onReady(); });
  function announce() {
    const index = wrap(Math.round(target));
    if (announced !== index) { announced = index; options.onChange(list[index], index, list.length); }
  }
  function resize() {
    const width = container.clientWidth, height = container.clientHeight; if (!width || !height) return;
    const halfHeight = width < 520 ? 2.85 : 2.65;
    camera.left = -halfHeight * width / height; camera.right = -camera.left;
    camera.top = halfHeight; camera.bottom = -halfHeight;
    camera.position.set(0, 8, 17); camera.lookAt(0, .5, 0);
    camera.updateProjectionMatrix(); renderer.setSize(width, height);
    sweepSpan = Math.min(7.5, Math.max(2.5, camera.right / .54 - 2));
  }
  const observer = new ResizeObserver(resize); observer.observe(container); resize(); announce();
  const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
  function pick(event) {
    const rect = canvas.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    return raycaster.intersectObjects(models.filter(model => model.visible), true)[0]?.object.userData.albumModel;
  }
  const listeners = [];
  function listen(name, handler, opts) { document.addEventListener(name, handler, opts); listeners.push([name, handler, opts]); }
  const isControl = event => event.target.closest('button,a,input,select,textarea,dialog');
  listen('pointerdown', event => {
    if (!active || event.button !== 0 || drag || isControl(event)) return;
    clearTimeout(snapTimer); drag = { id: event.pointerId, x: event.clientX, startX: event.clientX, startY: event.clientY, moved: false };
    resumeWaveAt = motionTime + 1.5;
    canvas.setPointerCapture(event.pointerId); canvas.style.cursor = 'grabbing';
  });
  listen('pointermove', event => {
    if (!active) return;
    if (drag && drag.id === event.pointerId) {
      if (Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) > 6) drag.moved = true;
      target -= (event.clientX - drag.x) / Math.max(130, container.clientWidth * .17);
      drag.x = event.clientX; hovered = null; resumeWaveAt = motionTime + 1.5; announce();
    } else {
      hovered = isControl(event) ? null : pick(event);
      if (hovered) resumeWaveAt = motionTime + 1.5;
      canvas.style.cursor = hovered ? 'pointer' : 'grab';
    }
  });
  function endDrag(event, cancelled = false) {
    if (!drag || event.pointerId !== drag.id) return;
    const clicked = !drag.moved && !cancelled; drag = null;
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
    canvas.style.cursor = 'grab'; target = Math.round(target); announce();
    if (clicked) { const model = pick(event); if (model) options.onSelect(model.userData.album); }
  }
  listen('pointerup', event => endDrag(event)); listen('pointercancel', event => endDrag(event, true));
  canvas.addEventListener('lostpointercapture', event => endDrag(event, true));
  listen('wheel', event => {
    if (!active || event.ctrlKey || isControl(event)) return;
    event.preventDefault();
    hovered = null; resumeWaveAt = motionTime + 1.5;
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? innerHeight : 1;
    target += THREE.MathUtils.clamp((Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY) * unit * .0065, -.8, .8);
    announce(); clearTimeout(snapTimer); snapTimer = setTimeout(() => { target = Math.round(target); announce(); }, 130);
  }, { passive: false });
  let previous = performance.now();
  renderer.setAnimationLoop(now => {
    const dt = Math.min((now - previous) / 1000, .05); previous = now; if (!active || document.hidden) return;
    motionTime += dt;
    current = reducedMotion ? target : THREE.MathUtils.damp(current, target, drag ? 20 : 8, dt);
    const span = Math.min(sweepSpan, (list.length - 1) / 2);
    let crest = waveCenter;
    if (hovered) crest = wrap(list.indexOf(hovered.userData.album) - current + list.length / 2) - list.length / 2;
    else if (motionEnabled && motionTime >= resumeWaveAt && !drag) crest = Math.sin(motionTime * 1.7 - Math.PI / 2) * span;
    else if (drag || motionTime < resumeWaveAt) crest = 0;
    waveCenter = reducedMotion ? crest : THREE.MathUtils.damp(waveCenter, crest, hovered ? 12 : 8, dt);
    models.forEach(model => {
      const index = list.indexOf(model.userData.album); model.visible = index !== -1; if (!model.visible) return;
      let offset = wrap(index - current + list.length / 2) - list.length / 2;
      if (list.length === 1) offset = 0;
      // Thin cards follow the diagonal reference arrangement. A moving crest
      // raises nearby cards without a spine or page-block silhouette.
      const influence = Math.exp(-Math.pow((offset - waveCenter) / 1.55, 2));
      const lift = (motionEnabled || hovered || drag ? influence * 1.18 : 0);
      model.userData.lift = reducedMotion ? lift : THREE.MathUtils.damp(model.userData.lift, lift, 10, dt);
      model.position.set(offset * .54, -.34 + model.userData.lift, offset * .29);
      model.rotation.set(0, 1.07 + model.userData.lift * .035, 0);
      model.scale.setScalar(1);
    });
    renderer.render(scene, camera);
  });
  return {
    step(direction) { target = Math.round(target) + direction; resumeWaveAt = motionTime + 1.5; announce(); },
    setAlbums(next) { list = next; target = current = 0; announced = -1; hovered = null; waveCenter = 0; announce(); },
    toggleMotion() { motionEnabled = !motionEnabled; options.onMotionChange?.(motionEnabled); return motionEnabled; },
    setActive(value) { active = value; drag = null; hovered = null; clearTimeout(snapTimer); target = Math.round(target); canvas.style.cursor = 'grab'; },
    dispose() {
      disposed = true; clearTimeout(snapTimer); observer.disconnect(); renderer.setAnimationLoop(null);
      listeners.forEach(([name, handler, opts]) => document.removeEventListener(name, handler, opts));
      const geometries = new Set(), materials = new Set();
      scene.traverse(object => { if (object.geometry) geometries.add(object.geometry); if (object.material) materials.add(object.material); });
      geometries.forEach(item => item.dispose()); materials.forEach(item => item.dispose()); textures.forEach(item => item.dispose()); light.shadow.dispose(); renderer.dispose();
    },
  };
}
