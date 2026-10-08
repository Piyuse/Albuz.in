import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';

export function createMemoryRoom(container, albums, options) {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, .1, 100);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.8));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.15;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);
  const canvas = renderer.domElement;
  const room = new THREE.Group();
  scene.add(room);
  const textures = new Set();
  const albumModels = [];
  let disposed = false;
  let active = true;
  let seed = 51;
  const random = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

  scene.add(new THREE.HemisphereLight(0xfff5df, 0x827563, 2.4));
  const sun = new THREE.DirectionalLight(0xffe6b2, 3.6);
  sun.position.set(-5, 11, 8);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  Object.assign(sun.shadow.camera, { left: -10, right: 10, top: 11, bottom: -7, near: .1, far: 40 });
  sun.shadow.normalBias = .025;
  sun.shadow.bias = -.00015;
  scene.add(sun);
  const bounce = new THREE.DirectionalLight(0xe5eaf0, 1.1);
  bounce.position.set(7, 5, 8);
  scene.add(bounce);

  function canvasTexture(width, height, paint) {
    const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
    paint(canvas.getContext('2d'), width, height);
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy()); textures.add(texture);
    return texture;
  }
  const grain = canvasTexture(512, 256, (ctx, w, h) => {
    ctx.fillStyle = '#b99970'; ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 1400; i++) {
      const y = random() * h;
      ctx.strokeStyle = random() > .5 ? `rgba(82,53,22,${random() * .13})` : `rgba(251,230,182,${random() * .2})`;
      ctx.lineWidth = random() * 1.4 + .2; ctx.beginPath(); ctx.moveTo(0, y);
      ctx.bezierCurveTo(150, y + 5, 360, y - 4, w, y + random() * 3); ctx.stroke();
    }
  });
  const linen = canvasTexture(256, 256, (ctx, w, h) => {
    ctx.fillStyle = '#a0a0a0'; ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 21000; i++) {
      const light = Math.floor(90 + random() * 110); ctx.fillStyle = `rgb(${light},${light},${light})`;
      ctx.fillRect(random() * w, random() * h, 1, 1 + random() * 3);
    }
  });
  linen.wrapS = linen.wrapT = THREE.RepeatWrapping;
  linen.repeat.set(3, 3);
  const pages = canvasTexture(128, 512, (ctx, w, h) => {
    ctx.fillStyle = '#eee5d4'; ctx.fillRect(0, 0, w, h);
    for (let y = 0; y < h; y += 4) { ctx.fillStyle = `rgba(123,105,77,${random() * .22})`; ctx.fillRect(0, y, w, 1); }
  });
  const ivory = new THREE.MeshStandardMaterial({ color: 0xcac2aa, roughness: .82 });
  const insetPaint = new THREE.MeshStandardMaterial({ color: 0xa79d85, roughness: .98 });
  const plaster = new THREE.MeshStandardMaterial({ color: 0xcac0a8, roughness: 1 });
  const oak = new THREE.MeshStandardMaterial({ map: grain, roughness: .78 });
  const brass = new THREE.MeshStandardMaterial({ color: 0x766342, metalness: .7, roughness: .37 });
  const darkMetal = new THREE.MeshStandardMaterial({ color: 0x514b3e, metalness: .65, roughness: .48 });
  function box(w, h, d, x, y, z, material, parent = room, bevel = 0) {
    const geometry = bevel ? new RoundedBoxGeometry(w, h, d, 2, bevel) : new THREE.BoxGeometry(w, h, d);
    const mesh = new THREE.Mesh(geometry, material); mesh.position.set(x, y, z);
    mesh.castShadow = true; mesh.receiveShadow = true; parent.add(mesh); return mesh;
  }
  function cylinder(top, bottom, height, x, y, z, material, parent = room) {
    const mesh = new THREE.Mesh(new THREE.CylinderGeometry(top, bottom, height, 32), material);
    mesh.position.set(x, y, z); mesh.castShadow = true; mesh.receiveShadow = true; parent.add(mesh); return mesh;
  }
  function cloth(color) { return new THREE.MeshStandardMaterial({ color, roughness: 1, bumpMap: linen, bumpScale: .035 }); }

  // Cutaway reading nook: plaster wall, inset window, oak floor and painted joinery.
  box(13.5, .24, 7, 0, -.2, 1.7, oak);
  for (let i = 0; i < 18; i++) {
    const plank = oak.clone(); plank.color.setScalar(.85 + random() * .22);
    box(.744, .045, 6.94, -6.35 + i * .75, -.065, 1.7, plank);
  }
  box(3.95, 7.7, .2, -4.64, 3.8, -1.08, plaster);
  box(3.95, 7.7, .2, 4.64, 3.8, -1.08, plaster);
  box(5.35, 2.28, .2, 0, 1.1, -1.08, plaster);
  box(5.35, .68, .2, 0, 7.33, -1.08, plaster);
  box(13.35, .22, .16, 0, .09, -.88, ivory);
  box(13.35, .17, .35, 0, 7.7, -1, ivory);

  // Shared photograph loading is local; no network request is needed at runtime.
  const photos = new Map();
  const imageLoads = [...new Set(albums.map(a => a.photo))].map(path => new Promise(resolve => {
    const image = new Image(); image.onload = () => { photos.set(path, image); resolve(); }; image.onerror = resolve; image.src = path;
  }));
  const loader = new THREE.TextureLoader();
  let sea;
  imageLoads.push(new Promise(resolve => {
    sea = loader.load('/memories/window-sea.png', texture => {
      // Crop to the window's aspect ratio rather than stretching the coastline or birds.
      const imageAspect = texture.image.width / texture.image.height;
      const windowAspect = 5.38 / 4.86;
      if (imageAspect > windowAspect) {
        texture.repeat.x = windowAspect / imageAspect;
        texture.offset.x = (1 - texture.repeat.x) / 2;
      } else {
        texture.repeat.y = imageAspect / windowAspect;
        texture.offset.y = (1 - texture.repeat.y) / 2;
      }
      resolve();
    }, undefined, resolve);
  }));
  textures.add(sea);
  sea.colorSpace = THREE.SRGBColorSpace;
  sea.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
  const view = new THREE.Mesh(new THREE.PlaneGeometry(5.38, 4.86), new THREE.MeshBasicMaterial({ map: sea, toneMapped: false }));
  view.position.set(0, 4.58, -1.19); room.add(view);
  for (const x of [-2.67, 2.67]) box(.17, 5, .4, x, 4.57, -.86, ivory);
  for (const y of [2.17, 7.02]) box(5.5, .19, .44, 0, y, -.84, ivory);
  box(.12, 4.72, .24, 0, 4.57, -.8, ivory);
  box(5.25, .13, .25, 0, 5.92, -.8, ivory);
  box(5.74, .15, .96, 0, 2.16, -.61, ivory, room, .025);
  box(5.46, .17, .16, 0, 6.03, -.52, oak);
  // Rolled linen blind above the window.
  const blind = cylinder(.13, .13, 5.22, 0, 6.95, -.59, cloth(0xb4a185)); blind.rotation.z = Math.PI / 2;

  function makeShelf(centerX) {
    const width = 2.72;
    box(width, 6.96, .12, centerX, 3.49, -.79, insetPaint);
    for (const x of [centerX - width / 2, centerX + width / 2]) {
      box(.18, 7.05, 1.37, x, 3.52, -.17, ivory);
      box(.24, 7.12, .12, x, 3.52, .55, ivory);
    }
    for (let row = 0; row < 7; row++) box(width, .15, 1.42, centerX, .29 + row * 1.08, -.12, ivory);
    box(width + .37, .23, 1.6, centerX, 7.02, -.13, ivory, room, .02);
    box(width + .4, .095, 1.66, centerX, 7.18, -.13, oak);
    box(width + .27, .28, 1.5, centerX, .04, -.1, ivory);
    // Small moulding creates a shadow line under every shelf lip.
    for (let row = 0; row < 7; row++) box(width, .055, .055, centerX, .245 + row * 1.08, .615, ivory);
  }
  makeShelf(-4.1); makeShelf(4.1);

  // Window seat and drawer fronts.
  box(5.3, 1.26, 2.1, 0, .6, .08, ivory);
  for (const x of [-1.75, 0, 1.75]) {
    box(1.68, .92, .09, x, .63, 1.15, insetPaint, room, .02);
    box(1.53, .78, .1, x, .64, 1.21, ivory, room, .025);
    box(.4, .043, .085, x, .82, 1.3, darkMetal, room, .015);
  }
  box(5.39, .17, 2.24, 0, 1.29, .1, ivory, room, .025);
  box(5.19, .35, 2.06, 0, 1.52, .12, cloth(0xd1c7b3), room, .14);
  function pillow(w, h, color, x, y, z, tilt) {
    const cushion = box(w, h, .31, x, y, z, cloth(color), room, .14);
    cushion.rotation.set(-.15, 0, tilt); return cushion;
  }
  pillow(.96, 1.02, 0xa69d85, 1.73, 2.07, -.32, -.12);
  pillow(.86, .84, 0xe0d1b8, 1.09, 1.99, -.09, .11);
  pillow(.7, .8, 0xab765d, .58, 1.95, .06, -.14);
  const throwMat = cloth(0xb9ad95);
  box(1.04, .025, 1.72, -1.4, 1.711, .42, throwMat, room, .008);
  box(1.04, .68, .025, -1.4, 1.37, 1.31, throwMat, room, .008);
  for (let i = 0; i < 12; i++) box(.008, .17, .008, -1.88 + i * .087, .97, 1.32, throwMat);

  // Woven rug with a restrained geometric border.
  const rugTexture = canvasTexture(1024, 768, (ctx, w, h) => {
    ctx.fillStyle = '#a6977c'; ctx.fillRect(0, 0, w, h);
    for (let i = 0; i < 34000; i++) { ctx.fillStyle = random() > .5 ? '#ffffff12' : '#473d3112'; ctx.fillRect(random() * w, random() * h, 3, 1); }
    for (const [inset, color, weight] of [[24, '#d4c8ab', 7], [47, '#746b58', 4], [83, '#c6b794', 23], [111, '#797966', 3]]) {
      ctx.strokeStyle = color; ctx.lineWidth = weight; ctx.strokeRect(inset, inset, w - inset * 2, h - inset * 2);
    }
    ctx.strokeStyle = '#6c756b88'; ctx.lineWidth = 9;
    for (let x = 172; x < w - 130; x += 145) for (let y = 174; y < h - 130; y += 145) {
      ctx.beginPath(); ctx.moveTo(x, y - 49); ctx.lineTo(x + 42, y); ctx.lineTo(x, y + 49); ctx.lineTo(x - 42, y); ctx.closePath(); ctx.stroke();
      ctx.fillStyle = '#d6c5a8'; ctx.fillRect(x - 7, y - 7, 14, 14);
    }
  });
  const rug = new THREE.Mesh(new THREE.PlaneGeometry(6.75, 3.3), new THREE.MeshStandardMaterial({ map: rugTexture, roughness: 1 }));
  rug.rotation.x = -Math.PI / 2; rug.position.set(-.3, -.027, 3.03); rug.receiveShadow = true; room.add(rug);

  // Upholstered chair, angled toward the window seat.
  const chair = new THREE.Group(); chair.position.set(4.45, 0, 3.22); chair.rotation.y = -.33; room.add(chair);
  const chairCloth = cloth(0xa89b7f);
  box(1.76, .5, 1.8, 0, .69, 0, chairCloth, chair, .18);
  box(1.37, .28, 1.35, 0, 1.04, .14, cloth(0xb9ab8e), chair, .13);
  const back = box(1.67, 1.54, .43, 0, 1.62, -.68, chairCloth, chair, .18); back.rotation.x = -.12;
  for (const x of [-.82, .82]) {
    box(.31, .63, 1.77, x, 1.2, 0, chairCloth, chair, .14);
    for (const z of [-.61, .61]) box(.13, .48, .13, x * .89, .27, z, oak, chair, .014);
  }
  const chairPillow = box(.77, .78, .2, .02, 1.63, -.25, cloth(0xd0b29b), chair, .13); chairPillow.rotation.z = -.1;
  // Reading light beside the chair.
  cylinder(.38, .43, .075, 5.61, .05, 1.59, darkMetal);
  cylinder(.035, .043, 2.8, 5.61, 1.48, 1.59, brass);
  const shadeMaterial = new THREE.MeshStandardMaterial({ color: 0xd1ab70, emissive: 0xf3bd6e, emissiveIntensity: .25, roughness: 1, side: THREE.DoubleSide });
  const shade = new THREE.Mesh(new THREE.CylinderGeometry(.34, .6, .64, 48, 1, true), shadeMaterial); shade.position.set(5.61, 2.93, 1.59); room.add(shade);
  const lamp = new THREE.PointLight(0xffb44d, 5, 4, 2); lamp.position.set(5.61, 2.84, 1.59); room.add(lamp);

  // Potted greenery is geometry, so it shares the room's perspective and shadows.
  const leafMaterial = new THREE.MeshStandardMaterial({ color: 0x4d6440, roughness: .95, side: THREE.DoubleSide });
  const leafGeometry = new THREE.SphereGeometry(1, 7, 5);
  function plant(x, y, z, scale) {
    const pot = new THREE.Group(); pot.position.set(x, y, z); pot.scale.setScalar(scale); room.add(pot);
    cylinder(.26, .2, .37, 0, .19, 0, new THREE.MeshStandardMaterial({ color: 0xa08256, roughness: .95 }), pot);
    cylinder(.235, .235, .02, 0, .38, 0, new THREE.MeshStandardMaterial({ color: 0x3e3629, roughness: 1 }), pot);
    for (let branch = 0; branch < 9; branch++) {
      const angle = branch * 2.4, height = .48 + random() * .52;
      const stem = new THREE.Mesh(new THREE.CylinderGeometry(.008, .015, height, 5), leafMaterial);
      stem.position.set(Math.sin(angle) * .12, .38 + height / 2, Math.cos(angle) * .12); stem.rotation.z = Math.sin(angle) * .35; pot.add(stem);
      for (let n = 0; n < 5; n++) {
        const leaf = new THREE.Mesh(leafGeometry, leafMaterial);
        leaf.scale.set(.13 + random() * .07, .035, .23);
        leaf.position.set(Math.sin(angle + n) * (.16 + random() * .17), .5 + n * height / 5, Math.cos(angle + n) * .22);
        leaf.rotation.set(random() * .6, angle + n, random() * .8); leaf.castShadow = true; pot.add(leaf);
      }
    }
  }
  plant(-4.48, 7.24, -.12, .85); plant(4.46, 7.24, -.22, .95);

  function frame(x, y, z, width, height, photo) {
    const frameGroup = new THREE.Group(); frameGroup.position.set(x, y, z); room.add(frameGroup);
    box(width, height, .08, 0, 0, 0, oak, frameGroup);
    box(width - .09, height - .09, .015, 0, 0, .05, new THREE.MeshStandardMaterial({ color: 0xe0d5bb, roughness: .9 }), frameGroup);
    const texture = loader.load(photo); texture.colorSpace = THREE.SRGBColorSpace; textures.add(texture);
    const art = new THREE.Mesh(new THREE.PlaneGeometry(width - .23, height - .23), new THREE.MeshStandardMaterial({ map: texture, roughness: .9 }));
    art.position.z = .064; frameGroup.add(art); return frameGroup;
  }
  frame(5.93, 4.85, -.9, .85, 1.18, '/memories/mountains.jpg');
  frame(5.93, 3.52, -.9, .85, 1.04, '/memories/lake.jpg');

  // Linen-bound albums: thick page blocks, separate covers and rounded labelled spines.
  const pendingCovers = [];
  function albumTexture(album, spine) {
    const width = spine ? 256 : 512, height = 768;
    const canvas = document.createElement('canvas'); canvas.width = width; canvas.height = height;
    const ctx = canvas.getContext('2d');
    const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy()); textures.add(texture);
    function paint() {
      ctx.fillStyle = album.color; ctx.fillRect(0, 0, width, height);
      for (let i = 0; i < 9500; i++) { ctx.fillStyle = random() > .5 ? '#ffffff0d' : '#00000012'; ctx.fillRect(random() * width, random() * height, 1, 2); }
      const shade = ctx.createLinearGradient(0, 0, width, 0); shade.addColorStop(0, '#00000028'); shade.addColorStop(.15, '#ffffff08'); shade.addColorStop(.8, '#00000000'); shade.addColorStop(1, '#00000022');
      ctx.fillStyle = shade; ctx.fillRect(0, 0, width, height);
      ctx.textAlign = 'center'; ctx.fillStyle = '#f4e5c8'; ctx.strokeStyle = '#dfc29488'; ctx.lineWidth = 2;
      ctx.strokeRect(17, 22, width - 34, height - 44);
      if (spine) {
        ctx.font = '20px Georgia'; ctx.fillText('M E M O R I E S', width / 2, 74, width - 45);
        const words = album.title.split(' '); const lines = []; let line = '';
        ctx.font = '36px Georgia';
        words.forEach(word => { if (ctx.measureText(`${line} ${word}`.trim()).width > width - 39 && line) { lines.push(line); line = word; } else line = `${line} ${word}`.trim(); }); lines.push(line);
        lines.forEach((text, index) => ctx.fillText(text, width / 2, 199 + index * 44, width - 33));
        const photo = photos.get(album.photo);
        if (photo) { ctx.fillStyle = '#dfd0b0'; ctx.fillRect(37, 391, width - 74, 144); ctx.drawImage(photo, 42, 396, width - 84, 134); }
        ctx.fillStyle = '#f4e5c8'; ctx.font = '36px Georgia'; ctx.fillText(album.year, width / 2, 645);
        ctx.font = '28px Georgia'; ctx.fillText('✦', width / 2, 702);
      } else {
        ctx.font = '42px Georgia';
        const words = album.title.split(' '); const lines = []; let line = '';
        words.forEach(word => { if (ctx.measureText(`${line} ${word}`.trim()).width > width - 90 && line) { lines.push(line); line = word; } else line = `${line} ${word}`.trim(); }); lines.push(line);
        lines.forEach((text, index) => ctx.fillText(text, width / 2, 107 + index * 53, width - 80));
        const photo = photos.get(album.photo);
        if (photo) { ctx.fillStyle = '#dfd0b0'; ctx.fillRect(61, 276, width - 122, 301); ctx.drawImage(photo, 68, 283, width - 136, 287); }
        ctx.fillStyle = '#f4e5c8'; ctx.font = '28px Georgia'; ctx.fillText(album.year, width / 2, 658);
        ctx.font = '17px Arial'; ctx.fillText('A COLLECTION OF MOMENTS', width / 2, 705);
      }
      texture.needsUpdate = true;
    }
    paint(); pendingCovers.push(paint); return texture;
  }
  const albumMaterials = albums.map(album => ({
    cover: new THREE.MeshStandardMaterial({ map: albumTexture(album, false), roughness: .88, bumpMap: linen, bumpScale: .013 }),
    spine: new THREE.MeshStandardMaterial({ map: albumTexture(album, true), roughness: .92, bumpMap: linen, bumpScale: .01 }),
    cloth: cloth(album.color),
  }));
  const pageMaterial = new THREE.MeshStandardMaterial({ map: pages, roughness: 1 });
  function makeAlbum(album, height, thickness, faceOut = false) {
    const model = new THREE.Group(); const m = albumMaterials[album.id];
    // Local X is the wide cover, local Z is the substantial album thickness.
    const width = .76, depth = thickness;
    box(width - .035, height - .06, depth - .045, 0, height / 2, 0, pageMaterial, model, .009);
    box(width, height, .03, 0, height / 2, depth / 2, m.cloth, model, .012);
    box(width, height, .03, 0, height / 2, -depth / 2, m.cloth, model, .012);
    box(.058, height, depth + .019, -width / 2 + .015, height / 2, 0, m.cloth, model, .02);
    const cover = new THREE.Mesh(new THREE.PlaneGeometry(width - .015, height - .02), m.cover); cover.position.set(0, height / 2, depth / 2 + .016); model.add(cover);
    const spine = new THREE.Mesh(new THREE.PlaneGeometry(depth + .013, height - .018), m.spine); spine.rotation.y = -Math.PI / 2; spine.position.set(-width / 2 - .017, height / 2, 0); model.add(spine);
    model.rotation.y = faceOut ? -.13 : Math.PI / 2;
    model.userData = { album, baseZ: 0 };
    model.traverse(child => { if (child.isMesh) child.userData.albumModel = model; });
    albumModels.push(model); room.add(model); return model;
  }
  for (let side = 0; side < 2; side++) {
    const centerX = side ? 4.1 : -4.1;
    for (let row = 0; row < 6; row++) {
      const baseY = .374 + row * 1.08;
      // Four generous spines per shelf; selected rows show a full album cover too.
      const featured = row === 2 || row === 4;
      let x = centerX - 1.19;
      const count = featured ? 3 : 5;
      for (let i = 0; i < count; i++) {
        const album = albums[(side * 12 + row * 4 + i) % albums.length];
        const thickness = featured ? .39 : .41 + (i % 2) * .025;
        const height = .81 + ((row + i) % 3) * .052;
        const model = makeAlbum(album, height, thickness);
        model.position.set(x + thickness / 2, baseY, .03 + (i % 2) * .018); model.userData.baseZ = model.position.z;
        x += thickness + .039;
      }
      if (featured) {
        const album = albums[(side * 12 + row * 4 + 3) % albums.length];
        const model = makeAlbum(album, .91, .21, true);
        model.position.set(centerX + .81, baseY, .22); model.userData.baseZ = .22;
      }
    }
  }
  Promise.all(imageLoads).then(() => { if (!disposed) { pendingCovers.forEach(paint => paint()); options.onReady(); } });

  // Entire-screen direct manipulation. Decorative UI never intercepts gestures.
  let compactView = container.clientWidth < 650;
  const bounds = { yaw: .65, panY: 1.35, panX: compactView ? 5 : 1.05 };
  const target = { yaw: -.08, panX: compactView ? 2.3 : 0, panY: 0 };
  const velocity = { x: 0, y: 0 };
  let drag = null, hovered = null, tapped = null;
  let tapTimer;
  function resize() {
    const width = container.clientWidth, height = container.clientHeight; if (!width || !height) return;
    camera.aspect = width / height;
    const nextCompactView = width < 650;
    if (compactView !== nextCompactView) {
      compactView = nextCompactView;
      target.panX = compactView ? 2.3 : 0;
      bounds.panX = compactView ? 5 : 1.05;
    }
    const halfHeight = 4.5, halfWidth = compactView ? 3 : 7.7;
    const distance = Math.max(halfHeight, halfWidth / camera.aspect) / Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    camera.position.set(distance * .16, 4.9 + distance * .075, distance);
    camera.lookAt(0, 3.7, .55);
    camera.updateProjectionMatrix(); renderer.setSize(width, height);
  }
  const observer = new ResizeObserver(resize); observer.observe(container); resize();
  const raycaster = new THREE.Raycaster(); const pointer = new THREE.Vector2();
  function pick(event) {
    const rect = canvas.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
    raycaster.setFromCamera(pointer, camera); scene.updateMatrixWorld(true);
    return raycaster.intersectObjects(room.children, true)[0]?.object.userData.albumModel || null;
  }
  const listeners = [];
  function listen(type, fn, opts) { document.addEventListener(type, fn, opts); listeners.push([type, fn, opts]); }
  function move(dx, dy) {
    target.yaw = THREE.MathUtils.clamp(target.yaw + dx, -bounds.yaw, bounds.yaw);
    target.panX = THREE.MathUtils.clamp(target.panX + dx * (compactView ? 4 : .5), -bounds.panX, bounds.panX);
    target.panY = THREE.MathUtils.clamp(target.panY + dy, -bounds.panY, bounds.panY);
  }
  function clearHighlight() { hovered = null; tapped = null; clearTimeout(tapTimer); options.onHover(null); }
  listen('pointerdown', event => {
    if (!active || event.button !== 0 || drag || event.target.closest('button,a,input,select,textarea')) return;
    drag = { id: event.pointerId, startX: event.clientX, startY: event.clientY, x: event.clientX, y: event.clientY, moved: false, time: performance.now() };
    velocity.x = velocity.y = 0; clearHighlight();
    canvas.setPointerCapture(event.pointerId); canvas.style.cursor = 'grabbing';
  });
  listen('pointermove', event => {
    if (!active) return;
    if (drag && event.pointerId === drag.id) {
      const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
      if (Math.hypot(event.clientX - drag.startX, event.clientY - drag.startY) > 5) drag.moved = true;
      move(dx * .0035, -dy * .009);
      const dt = Math.max(performance.now() - drag.time, 8) / 1000;
      velocity.x = THREE.MathUtils.clamp(dx * .0035 / dt, -1.2, 1.2);
      velocity.y = THREE.MathUtils.clamp(-dy * .009 / dt, -2.5, 2.5);
      drag.x = event.clientX; drag.y = event.clientY; drag.time = performance.now();
    } else if (event.pointerType !== 'touch' && !event.target.closest('button')) {
      hovered = pick(event); options.onHover(hovered?.userData.album || null);
      canvas.style.cursor = hovered ? 'pointer' : 'grab';
    }
  });
  listen('pointerup', event => {
    if (!active || !drag || drag.id !== event.pointerId) return;
    const clicked = !drag.moved;
    if (performance.now() - drag.time > 100) velocity.x = velocity.y = 0;
    drag = null;
    if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
    canvas.style.cursor = 'grab';
    if (clicked) {
      velocity.x = velocity.y = 0; tapped = pick(event);
      if (tapped) options.onSelect?.(tapped.userData.album);
    }
  });
  function cancelDrag() { drag = null; velocity.x = velocity.y = 0; canvas.style.cursor = 'grab'; }
  listen('pointercancel', cancelDrag);
  const onLostCapture = () => { if (drag) cancelDrag(); };
  canvas.addEventListener('lostpointercapture', onLostCapture);
  const onBlur = () => { cancelDrag(); clearHighlight(); };
  window.addEventListener('blur', onBlur);
  listen('wheel', event => {
    if (!active || event.ctrlKey) return; // Preserve browser/pinch zoom accessibility.
    event.preventDefault(); clearHighlight(); velocity.x = velocity.y = 0;
    const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? innerHeight : 1;
    const horizontal = event.shiftKey ? event.deltaY : event.deltaX;
    const vertical = event.shiftKey ? 0 : event.deltaY;
    move(-horizontal * unit * .0025, -vertical * unit * .004);
  }, { passive: false });

  let previous = performance.now();
  renderer.setAnimationLoop(now => {
    const dt = Math.min((now - previous) / 1000, .05); previous = now; if (document.hidden || !active) return;
    if (!drag && !reducedMotion) { move(velocity.x * dt, velocity.y * dt); velocity.x *= Math.exp(-9 * dt); velocity.y *= Math.exp(-9 * dt); }
    const damping = drag ? 28 : 11;
    room.rotation.y = reducedMotion ? target.yaw : THREE.MathUtils.damp(room.rotation.y, target.yaw, damping, dt);
    room.position.x = reducedMotion ? target.panX : THREE.MathUtils.damp(room.position.x, target.panX, damping, dt);
    room.position.y = reducedMotion ? target.panY : THREE.MathUtils.damp(room.position.y, target.panY, damping, dt);
    albumModels.forEach(model => {
      const forward = model === hovered || model === tapped ? .17 : 0;
      model.position.z = reducedMotion ? model.userData.baseZ + forward : THREE.MathUtils.damp(model.position.z, model.userData.baseZ + forward, 10, dt);
    });
    renderer.render(scene, camera);
  });
  return {
    setActive: value => {
      active = value;
      cancelDrag(); clearHighlight();
    },
    move: (x, y) => { velocity.x = velocity.y = 0; clearHighlight(); move(x, y); },
    reset: () => { Object.assign(target, { yaw: -.08, panX: compactView ? 2.3 : 0, panY: 0 }); velocity.x = velocity.y = 0; clearHighlight(); },
    dispose: () => {
      disposed = true; clearTimeout(tapTimer); renderer.setAnimationLoop(null); observer.disconnect();
      listeners.forEach(([name, fn, opts]) => document.removeEventListener(name, fn, opts));
      canvas.removeEventListener('lostpointercapture', onLostCapture); window.removeEventListener('blur', onBlur);
      const geometries = new Set(), materials = new Set();
      scene.traverse(object => { if (object.geometry) geometries.add(object.geometry); if (object.material) (Array.isArray(object.material) ? object.material : [object.material]).forEach(m => materials.add(m)); });
      geometries.forEach(g => g.dispose()); materials.forEach(m => m.dispose()); textures.forEach(t => t.dispose()); sun.shadow.dispose(); renderer.dispose();
    },
  };
}
