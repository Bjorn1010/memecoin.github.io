// Panier Onze : état persisté dans le navigateur, partagé entre les pages.

import { getProduct, formatPrice, hasFlocage, FLOCAGE_PRICE } from './onze-catalogue.js';

const STORAGE_KEY = 'onze:cart:v1';

const read = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    return [];
  }
};

const write = (lines) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(lines));
  } catch (error) {
    // Navigation privée / stockage bloqué : le panier reste en mémoire pour la session.
  }
  document.dispatchEvent(new CustomEvent('onze:cart-changed', { detail: { lines } }));
};

const lineKey = (line) => `${line.productId}|${line.size}|${line.flocageName || ''}|${line.flocageNumber || ''}`;

export const getLines = () => read();

export const getCount = () => read().reduce((total, line) => total + line.quantity, 0);

export const lineUnitPrice = (line) => {
  const product = getProduct(line.productId);
  const personalised = hasFlocage(product, { name: line.flocageName, number: line.flocageNumber });
  return product.price + (personalised ? FLOCAGE_PRICE : 0);
};

export const getTotal = () => read().reduce((total, line) => total + lineUnitPrice(line) * line.quantity, 0);

export const addLine = (line) => {
  const lines = read();
  const key = lineKey(line);
  const existing = lines.find((item) => lineKey(item) === key);
  if (existing) {
    existing.quantity = Math.min(existing.quantity + (line.quantity || 1), 20);
  } else {
    lines.push({ ...line, quantity: Math.min(line.quantity || 1, 20) });
  }
  write(lines);
  return lines;
};

export const setQuantity = (key, quantity) => {
  let lines = read();
  if (quantity <= 0) {
    lines = lines.filter((line) => lineKey(line) !== key);
  } else {
    const target = lines.find((line) => lineKey(line) === key);
    if (target) target.quantity = Math.min(quantity, 20);
  }
  write(lines);
  return lines;
};

export const removeLine = (key) => setQuantity(key, 0);

export const clear = () => write([]);

export const keyOf = lineKey;

// Met à jour la pastille du panier dans la navigation.
export const bindCartBadge = () => {
  const render = () => {
    const count = getCount();
    document.querySelectorAll('[data-cart-count]').forEach((el) => {
      el.textContent = count > 0 ? String(count) : '';
      el.classList.toggle('is-empty', count === 0);
    });
  };
  document.addEventListener('onze:cart-changed', render);
  window.addEventListener('storage', (event) => {
    if (event.key === STORAGE_KEY) render();
  });
  render();
};

export { formatPrice };
