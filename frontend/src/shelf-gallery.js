import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

const PITCH = .56;
const SPINE = .47;
const COVER = 2.1;
const EXTRA = COVER - PITCH;
const colors = ['#d66049', '#446e78', '#d8839a', '#c39b47', '#547758', '#3c5276', '#ba7155', '#5e7780'];

export function createAlbumGallery(container, albums, options) {
  const scene = new THREE.Scene();
  const camera = new THREE.OrthographicCamera(-5, 5, 2.65, -2.65, .1, 50);
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);
  const canvas = renderer.domElement;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const keyLight = new THREE.DirectionalLight(0xffffff, 3.2);
  keyLight.position.set(-4, 7, 9);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(1024, 1024);
  Object.assign(keyLight.shadow.camera, { left: -14, right: 14, top: 8, bottom: -8 });
  keyLight.shadow.normalBias = .025;
  scene.add(new THREE.HemisphereLight(0xffffff, 0xd2c3ae, 2.7), keyLight);
  const sideLight = new THREE.DirectionalLight(0xffefd8, 1.1);
  sideLight.position.set(6, 3, -5);
  scene.add(sideLight);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(80, 20), new THREE.ShadowMaterial({ opacity: .24 }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = -1.66;
  floor.receiveShadow = true;
  scene.add(floor);

  const textures = [], models = [];
  let disposed = false, active = true, list = albums;
  let current = 0, target = 0, announced = -1, drag = null, hovered = null, snapTimer;
  let motionEnabled = !reducedMotion, motionTime = 0, autoClock = 0, resumeAutoAt = 0;
  let opening = null, hoverNotified = false;
  const wrap = value => ((value % list.length) + list.length) % list.length;
  const relative = index => THREE.MathUtils.euclideanModulo(index - current + list.length / 2, list.length) - list.length / 2;
  const pauseAutoplay = () => { resumeAutoAt = motionTime + 5; autoClock = 0; };
  const nearestMatch = value => Math.round(value);
  const nextMatch = direction => Math.round(target) + direction;

  function box(parent, width, height, depth, material, x = 0, z = 0, radius = .025) {
    const object = new THREE.Mesh(new RoundedBoxGeometry(width, height, depth, 2, radius), material);
    object.position.set(x, 0, z);
    object.castShadow = true;
    object.receiveShadow = true;
    parent.add(object);
    return object;
  }
  function texture(width, height, paint) {
    const surface = document.createElement('canvas');
    surface.width = width; surface.height = height;
    const context = surface.getContext('2d');
    const map = new THREE.CanvasTexture(surface);
    map.colorSpace = THREE.SRGBColorSpace;
    map.anisotropy = renderer.capabilities.getMaxAnisotropy();
    textures.push(map);
    const update = photo => { paint(context, photo); map.needsUpdate = true; };
    update(null);
    return { map, update };
  }
  function coverTexture(album, color) {
    return texture(780, 1100, (ctx, photo) => {
      ctx.fillStyle = color; ctx.fillRect(0, 0, 780, 1100);
      const sheen = ctx.createLinearGradient(0, 0, 780, 1100);
      sheen.addColorStop(0, '#ffffff35'); sheen.addColorStop(.5, '#ffffff00'); sheen.addColorStop(1, '#00000032');
      ctx.fillStyle = sheen; ctx.fillRect(0, 0, 780, 1100);
      ctx.strokeStyle = '#fff9e599'; ctx.lineWidth = 3; ctx.strokeRect(28, 28, 724, 1044);
      ctx.fillStyle = '#fff9eb'; ctx.textAlign = 'center'; ctx.font = '24px Arial';
      ctx.letterSpacing = '5px'; ctx.fillText('S T I L L S   /   M E M O R I E S', 390, 102); ctx.letterSpacing = '0px';
      ctx.fillStyle = '#eee0c8'; ctx.fillRect(87, 164, 606, 514);
      if (photo) {
        const width = 584, height = 492;
        const scale = Math.max(width / photo.width, height / photo.height);
        const sourceWidth = width / scale, sourceHeight = height / scale;
        ctx.drawImage(photo, (photo.width - sourceWidth) / 2, (photo.height - sourceHeight) / 2, sourceWidth, sourceHeight, 98, 175, width, height);
      }
      ctx.fillStyle = '#fff9eb'; ctx.font = '76px Georgia';
      const words = album.title.split(' '), lines = []; let line = '';
      for (const word of words) {
        const next = `${line} ${word}`.trim();
        if (line && ctx.measureText(next).width > 620) { lines.push(line); line = word; } else line = next;
      }
      lines.push(line);
      lines.slice(0, 3).forEach((text, index) => ctx.fillText(text, 390, 790 + index * 86, 650));
      ctx.font = '25px Arial'; ctx.letterSpacing = '5px'; ctx.fillText(album.year, 390, 1020); ctx.letterSpacing = '0px';
    });
  }
  function spineTexture(album, color) {
    return texture(170, 1000, ctx => {
      ctx.fillStyle = color; ctx.fillRect(0, 0, 170, 1000);
      const shade = ctx.createLinearGradient(0, 0, 170, 0);
      shade.addColorStop(0, '#0000003a'); shade.addColorStop(.3, '#ffffff20'); shade.addColorStop(.8, '#ffffff00'); shade.addColorStop(1, '#00000040');
      ctx.fillStyle = shade; ctx.fillRect(0, 0, 170, 1000);
      ctx.fillStyle = '#fff9ed'; ctx.textAlign = 'center'; ctx.font = '33px Georgia'; ctx.fillText('✦', 85, 94);
      ctx.save(); ctx.translate(85, 510); ctx.rotate(-Math.PI / 2);
      ctx.font = 'bold 69px Georgia'; ctx.fillText(album.title, 0, 22, 680); ctx.restore();
      ctx.font = '26px Arial'; ctx.fillText(album.year, 85, 938);
    });
  }

  const loads = albums.map((album, index) => {
    const color = album.color || colors[index % colors.length];
    const height = 3.28 + [0, .17, -.08, .24, .06, .28, -.03, .14][index % 8];
    const model = new THREE.Group();
    model.userData.album = album; model.userData.height = height;
    model.userData.hoverLift = 0;
    scene.add(model); models.push(model);
    const cloth = new THREE.MeshStandardMaterial({ color, roughness: .7, metalness: .02 });
    box(model, SPINE, height, .32, cloth, 0, 0, .035);
    const spine = spineTexture(album, color);
    const spineFace = new THREE.Mesh(new THREE.PlaneGeometry(SPINE - .045, height - .045), new THREE.MeshBasicMaterial({ map: spine.map, toneMapped: false }));
    spineFace.position.z = .166; model.add(spineFace);
    const pivot = new THREE.Group(); pivot.position.set(-SPINE / 2 + .02, 0, .15);
    model.add(pivot); model.userData.pivot = pivot;
    box(pivot, COVER, height, .12, cloth, COVER / 2, .015);
    const paper = new THREE.MeshStandardMaterial({ color: 0xf2e8d8, roughness: .95 });
    box(pivot, COVER - .09, height - .1, .035, paper, COVER / 2 + .025, -.061, .012);
    const cover = coverTexture(album, color);
    const front = new THREE.Mesh(new THREE.PlaneGeometry(COVER - .055, height - .055), new THREE.MeshBasicMaterial({ map: cover.map, toneMapped: false, side: THREE.DoubleSide }));
    front.position.set(COVER / 2, 0, .081); pivot.add(front);
    model.traverse(child => { if (child.isMesh) child.userData.albumModel = model; });
    return new Promise(resolve => {
      const photo = new Image();
      photo.onload = () => { if (!disposed) cover.update(photo); resolve(); };
      photo.onerror = resolve; photo.src = album.photo;
    });
  });
  Promise.all(loads).then(() => { if (!disposed) options.onReady(); });

  function announce() {
    if (!list.length) return;
    const index = wrap(nearestMatch(target));
    if (index !== announced) { announced = index; options.onChange(list[index], index, list.length); }
  }
  function resize() {
    const width = container.clientWidth, height = container.clientHeight;
    if (!width || !height) return;
    const halfHeight = width < 520 ? 2.38 : 2.42;
    camera.left = -halfHeight * width / height; camera.right = -camera.left;
    camera.top = halfHeight; camera.bottom = -halfHeight;
    camera.position.set(0, .1, 13); camera.lookAt(0, .1, 0);
    camera.updateProjectionMatrix(); renderer.setSize(width, height);
  }
  const observer = new ResizeObserver(resize); observer.observe(container); resize(); announce();
  const raycaster = new THREE.Raycaster(), pointer = new THREE.Vector2();
  function pick(event) {
    const rect = canvas.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    return raycaster.intersectObjects(models.filter(model => model.visible), true)[0]?.object.userData.albumModel;
  }
  function notifyHover() {
    if (!hovered || opening || !active) {
      if (hoverNotified) { options.onHover?.(null); hoverNotified = false; }
      return;
    }
    const top = -1.65 + hovered.userData.height + hovered.userData.hoverLift + .2;
    const center = hovered.position.x + (hovered.userData.openness || 0) * (COVER - SPINE) / 2;
    const point = new THREE.Vector3(center, top, .2).project(camera);
    options.onHover?.(hovered.userData.album, {
      x: THREE.MathUtils.clamp((point.x + 1) * container.clientWidth / 2, 88, container.clientWidth - 88),
      y: Math.max(42, (1 - point.y) * container.clientHeight / 2 - 10),
    });
    hoverNotified = true;
  }
  function beginOpen(album) {
    if (!active || opening) return;
    const model = models.find(item => item.userData.album === album);
    if (!model) return;
    if (reducedMotion) { options.onSelect(album); return; }
    const index = list.indexOf(album);
    if (index < 0) return;
    target = index + Math.round((target - index) / list.length) * list.length;
    pauseAutoplay(); hovered = null; notifyHover(); announce();
    opening = { model, time: 0, startAngle: model.userData.pivot.rotation.y };
  }
  const listeners = [];
  function listen(type, handler, opts) { document.addEventListener(type, handler, opts); listeners.push([type, handler, opts]); }
  const isControl = event => event.target.closest('button,a,input,select,textarea,dialog');
  listen('pointerdown', event => {
    if (!active || opening || event.button !== 0 || drag || isControl(event)) return;
    clearTimeout(snapTimer); pauseAutoplay();
    drag = { id: event.pointerId, x: event.clientX, startX: event.clientX, startY: event.clientY, moved: false };
    canvas.setPointerCapture(event.pointerId); canvas.style.cursor = 'grabbing';
  });
  listen('pointermove', event => {
    if (!active || opening) return;
    if (drag && drag.id === event.pointerId) {
      if (Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) > 6) drag.moved = true;
      target -= (event.clientX - drag.x) / Math.max(75, container.clientWidth * .12);
      drag.x = event.clientX; hovered = null; announce();
    } else { hovered = isControl(event) ? null : pick(event); canvas.style.cursor = hovered ? 'pointer' : 'grab'; }
  });
  function endDrag(event, cancelled = false) {
    if (!drag || event.pointerId !== drag.id) return;
    const clicked = !drag.moved && !cancelled; drag = null;
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
    canvas.style.cursor = 'grab'; target = nearestMatch(target); announce();
    if (clicked) { const model = pick(event); if (model) beginOpen(model.userData.album); }
  }
  listen('pointerup', event => endDrag(event)); listen('pointercancel', event => endDrag(event, true));
  canvas.addEventListener('lostpointercapture', event => endDrag(event, true));
  listen('wheel', event => {
    if (!active || opening || event.ctrlKey || isControl(event)) return;
    event.preventDefault(); pauseAutoplay();
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? innerHeight : 1;
    const delta = (Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : event.deltaY) * unit;
    target += THREE.MathUtils.clamp(delta * .008, -.9, .9); announce();
    clearTimeout(snapTimer); snapTimer = setTimeout(() => { target = nearestMatch(target); announce(); }, 140);
  }, { passive: false });

  let previous = performance.now();
  renderer.setAnimationLoop(now => {
    const dt = Math.min((now - previous) / 1000, .05); previous = now;
    if (!active || document.hidden) return;
    motionTime += dt;
    if (motionEnabled && list.length === albums.length && !drag && motionTime >= resumeAutoAt && list.length > 1) {
      autoClock += dt;
      if (autoClock > 3.5) { target = nextMatch(1); autoClock = 0; announce(); }
    }
    if (reducedMotion) current = target;
    else {
      const eased = THREE.MathUtils.damp(current, target, 3.6, dt);
      current += THREE.MathUtils.clamp(eased - current, -4 * dt, 4 * dt);
    }
    const entries = models.map(model => {
      const index = list.indexOf(model.userData.album);
      model.visible = index !== -1;
      if (index < 0) return null;
      const offset = list.length === 1 ? 0 : relative(index);
      const openness = THREE.MathUtils.smoothstep(Math.max(0, 1 - Math.abs(offset)), 0, 1);
      model.userData.openness = openness;
      return { model, offset, openness };
    }).filter(Boolean).sort((a, b) => a.offset - b.offset);
    const expansion = entries.reduce((sum, entry) => sum + entry.openness * EXTRA, 0);
    let added = 0;
    for (const { model, offset, openness } of entries) {
      const user = model.userData;
      user.hoverLift = THREE.MathUtils.damp(user.hoverLift, hovered === model && !opening ? .12 : 0, 12, dt);
      model.position.set(offset * PITCH + added - expansion / 2, -1.65 + user.height / 2 + user.hoverLift, user.hoverLift * .7);
      model.rotation.z = THREE.MathUtils.damp(model.rotation.z, hovered === model && !opening ? -.018 : 0, 12, dt);
      model.scale.setScalar(1);
      model.userData.pivot.rotation.y = -(1 - openness) * Math.PI / 2;
      added += openness * EXTRA;
    }
    notifyHover();
    if (opening) {
      opening.time += dt;
      const progress = Math.min(1, opening.time / .82);
      const ease = value => value * value * (3 - 2 * value);
      const pivot = opening.model.userData.pivot;
      pivot.rotation.y = progress < .52
        ? THREE.MathUtils.lerp(opening.startAngle, 0, ease(progress / .52))
        : THREE.MathUtils.lerp(0, -Math.PI * .64, ease((progress - .52) / .48));
      opening.model.position.z += .92 * ease(progress);
      opening.model.position.y += .09 * ease(progress);
      opening.model.scale.multiplyScalar(1 + .11 * ease(progress));
      if (progress === 1) {
        const album = opening.model.userData.album;
        opening = null;
        options.onSelect(album);
      }
    }
    renderer.render(scene, camera);
  });
  return {
    step(direction) { hovered = null; notifyHover(); target = nextMatch(direction); pauseAutoplay(); announce(); },
    open: beginOpen,
    setAlbums(next) {
      if (!next.length) return;
      list = next;
      current = target = 0;
      announced = -1;
      hovered = null;
      models.forEach(model => { model.visible = list.includes(model.userData.album); });
      pauseAutoplay(); notifyHover(); announce();
    },
    toggleMotion() { motionEnabled = !motionEnabled; return motionEnabled; },
    setActive(value) { active = value; drag = null; hovered = null; opening = null; clearTimeout(snapTimer); target = nearestMatch(target); canvas.style.cursor = 'grab'; notifyHover(); if (value) pauseAutoplay(); },
    dispose() {
      disposed = true; clearTimeout(snapTimer); observer.disconnect(); renderer.setAnimationLoop(null);
      listeners.forEach(([type, handler, opts]) => document.removeEventListener(type, handler, opts));
      const geometries = new Set(), materials = new Set();
      scene.traverse(object => { if (object.geometry) geometries.add(object.geometry); if (object.material) materials.add(object.material); });
      geometries.forEach(geometry => geometry.dispose()); materials.forEach(material => material.dispose());
      textures.forEach(map => map.dispose()); keyLight.shadow.dispose(); renderer.dispose();
    },
  };
}
