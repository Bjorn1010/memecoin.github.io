// Composants d'interface partagés par les pages boutique.

import { SHIPPING, formatPrice, whatsappLink } from './onze-catalogue.js';

export const renderShippingProgress = (el, subtotal) => {
  if (!el) return;
  const remaining = Math.max(0, SHIPPING.freeFrom - subtotal);
  const ratio = Math.min(1, subtotal / SHIPPING.freeFrom);
  el.hidden = subtotal === 0;
  el.classList.toggle('is-complete', remaining === 0);
  el.innerHTML = `
    <p class="shipping-progress__label"></p>
    <div class="shipping-progress__track" role="progressbar" aria-valuemin="0" aria-valuemax="${SHIPPING.freeFrom}"
      aria-valuenow="${Math.min(subtotal, SHIPPING.freeFrom)}" aria-label="Progression vers la livraison offerte">
      <div class="shipping-progress__bar" style="width: ${(ratio * 100).toFixed(1)}%"></div>
    </div>
  `;
  el.querySelector('.shipping-progress__label').textContent =
    remaining === 0
      ? 'Livraison offerte débloquée'
      : `Plus que ${formatPrice(remaining)} pour la livraison offerte`;
};

export const mountWhatsAppButton = (message = 'Bonjour Onze, j’ai une question :') => {
  if (document.querySelector('.wa-float')) return;
  const link = document.createElement('a');
  link.className = 'wa-float';
  link.href = whatsappLink(message);
  link.target = '_blank';
  link.rel = 'noopener';
  link.setAttribute('aria-label', 'Nous écrire sur WhatsApp');
  link.innerHTML = `
    <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true" focusable="false">
      <path fill="currentColor" d="M12.04 2a9.9 9.9 0 0 0-8.5 14.96L2 22l5.2-1.5A9.9 9.9 0 1 0 12.04 2Zm0 18.1a8.2 8.2 0 0 1-4.2-1.15l-.3-.18-3.08.89.9-3-.2-.31a8.2 8.2 0 1 1 6.88 3.75Zm4.5-6.14c-.25-.12-1.46-.72-1.69-.8-.22-.08-.39-.12-.55.13-.16.24-.63.8-.77.96-.14.16-.28.18-.53.06a6.7 6.7 0 0 1-3.34-2.92c-.25-.43.25-.4.72-1.34.08-.16.04-.3-.02-.42-.06-.12-.55-1.33-.76-1.82-.2-.48-.4-.41-.55-.42h-.47a.9.9 0 0 0-.65.3 2.74 2.74 0 0 0-.86 2.04 4.76 4.76 0 0 0 1 2.53 10.9 10.9 0 0 0 4.17 3.68c1.55.67 2.16.73 2.94.61.47-.07 1.46-.6 1.66-1.17.2-.58.2-1.07.14-1.17-.06-.1-.22-.16-.47-.28Z"/>
    </svg>
  `;
  document.body.appendChild(link);
};
