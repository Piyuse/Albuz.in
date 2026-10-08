import { mkdir, writeFile } from 'node:fs/promises';
const isbns = ['9780743273565','9780451524935','9780141439518','9780061120084','9780316769488','9780547928227','9780441172719','9780140283334','9780307387899','9780141439556','9780142437209','9780156012195','9780060850524','9780141187761','9780140449136','9780140268867','9780141439471','9780553213119','9780140449266','9780141439846','9780142437230','9780141441146','9780141439600','9780141439662'];
await mkdir('public/covers', { recursive: true });
let next = 0;
await Promise.all(Array.from({length:4}, async () => {
  while(next < isbns.length) {
    const isbn = isbns[next++];
    try {
      const response = await fetch(`https://covers.openlibrary.org/b/isbn/${isbn}-M.jpg?default=false`, {signal:AbortSignal.timeout(20000)});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      await writeFile(`public/covers/${isbn}.jpg`, Buffer.from(await response.arrayBuffer()));
      console.log(`${isbn}: downloaded`);
    } catch (e) { console.log(`${isbn}: ${e.message}`); }
  }
}));

