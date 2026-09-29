// Génère une page HTML par maillot à partir de produit.html, avec titre,
// description, image de partage et adresse canonique propres à chaque produit
// (les robots et les aperçus de liens ne lisent pas le JavaScript).
// Usage : node onze-store/tools/build-product-pages.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const BASE = 'https://bjorn1010.github.io/memecoin.github.io/onze-store/';
const { PRODUCTS, productImage, productPagePath } = await import(pathToFileURL(path.join(root, 'assets/js/onze-catalogue.js')).href);

const template = fs.readFileSync(path.join(root, 'produit.html'), 'utf8');
const escape = (s) => s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
const setMeta = (html, attr, key, value) =>
  html.replace(new RegExp(`<meta content="[^"]*" ${attr}="${key}" />`), `<meta content="${escape(value)}" ${attr}="${key}" />`);

for (const product of PRODUCTS) {
  const name = `${product.name1} ${product.name2}`;
  const title = `Maillot ${name} — Onze`;
  const description = `${product.tagline} ${product.description}`.slice(0, 200);
  const url = BASE + productPagePath(product);
  const image = BASE + productImage(product);

  // produit.html?id=… reste accessible mais non indexé : seules les pages générées le sont.
  let html = template.replace('    <meta content="noindex,follow" name="robots" />\n', '').replace(/<title>[^<]*<\/title>/, `<title>${escape(title)}</title>`);
  html = setMeta(html, 'name', 'description', description);
  html = setMeta(html, 'property', 'og:title', title);
  html = setMeta(html, 'property', 'og:description', description);
  html = setMeta(html, 'property', 'og:image', image);
  html = setMeta(html, 'name', 'twitter:title', title);
  html = setMeta(html, 'name', 'twitter:description', description);
  html = html.replace(/<link href="[^"]*" rel="canonical" id="canonical-link" \/>/, `<link href="${url}" rel="canonical" id="canonical-link" />`);
  html = html.replace('<meta content="width=device-width, initial-scale=1" name="viewport" />', `<meta content="width=device-width, initial-scale=1" name="viewport" />\n    <meta content="${product.id}" name="onze-product" />\n    <meta content="${image}" name="twitter:image" />`);
  fs.writeFileSync(path.join(root, productPagePath(product)), html);
}

// Les pages légales, le panier et la commande sont en noindex : hors sitemap.
const pages = ['index.html', 'boutique.html', 'a-propos.html'].filter((p) => fs.existsSync(path.join(root, p)));
const urls = [...pages, ...PRODUCTS.map(productPagePath)].map((p) => {
  const loc = p === 'index.html' ? BASE : BASE + p;
  const priority = p === 'index.html' ? '1.0' : p.startsWith('maillot-') || p === 'boutique.html' ? '0.8' : '0.4';
  return `  <url><loc>${loc}</loc><priority>${priority}</priority></url>`;
});
fs.writeFileSync(path.join(root, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join('\n')}\n</urlset>\n`);
console.log(`${PRODUCTS.length} pages produit + sitemap (${urls.length} URL)`);
