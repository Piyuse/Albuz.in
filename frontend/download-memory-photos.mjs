import { mkdir, writeFile } from 'node:fs/promises';
const photos = {
  lake: 'photo-1470770841072-f978cf4d019e',
  mountains: 'photo-1464822759023-fed622ff2c3b',
  coast: 'photo-1518837695005-2083093ee35b',
  italy: 'photo-1516483638261-f4dbaf036963',
  forest: 'photo-1441974231531-c6227db76b6e',
  stars: 'photo-1519681393784-d120267933ba',
};
await mkdir('public/memories', { recursive: true });
await Promise.all(Object.entries(photos).map(async ([name, id]) => {
  const response = await fetch(`https://images.unsplash.com/${id}?auto=format&fit=crop&w=${name === 'forest' ? 1400 : 600}&q=85`, { signal: AbortSignal.timeout(30000) });
  if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
  await writeFile(`public/memories/${name}.jpg`, Buffer.from(await response.arrayBuffer()));
  console.log(`${name}: saved`);
}));
