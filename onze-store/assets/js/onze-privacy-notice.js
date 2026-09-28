// Bandeau d'information vie privée : ce site ne dépose aucun cookie de mesure
// d'audience ni de service tiers, seul le panier est mémorisé en localStorage
// (donnée strictement nécessaire, sans consentement requis). Affiché une fois
// par navigateur, purement informatif.
(function () {
  var STORAGE_KEY = 'onze:privacy-notice-dismissed:v1';

  var dismissed = false;
  try {
    dismissed = localStorage.getItem(STORAGE_KEY) === '1';
  } catch (e) {
    dismissed = false;
  }
  if (dismissed) return;

  function init() {
    var style = document.createElement('style');
    style.textContent = [
      '.onze-privacy-notice{position:fixed;left:1rem;right:1rem;bottom:1rem;z-index:9999;',
      'display:flex;flex-wrap:wrap;align-items:center;gap:0.75rem;',
      'max-width:34rem;margin:0 auto;padding:0.9rem 1.1rem;border-radius:0.6rem;',
      'background:#141416;color:#e8e8ea;border:1px solid rgba(255,255,255,0.12);',
      'font:400 0.8rem/1.4 inherit;box-shadow:0 0.5rem 1.5rem rgba(0,0,0,0.35);}',
      '.onze-privacy-notice p{margin:0;flex:1 1 16rem;}',
      '.onze-privacy-notice a{color:inherit;text-decoration:underline;}',
      '.onze-privacy-notice button{flex:0 0 auto;border:1px solid rgba(255,255,255,0.25);',
      'background:transparent;color:inherit;border-radius:0.4rem;padding:0.4rem 0.9rem;',
      'font:inherit;cursor:pointer;}',
      '.onze-privacy-notice button:hover{background:rgba(255,255,255,0.1);}',
      '@media (min-width:900px){.onze-privacy-notice{right:auto;max-width:26rem;margin:0;}}',
    ].join('');
    document.head.appendChild(style);

    var bar = document.createElement('div');
    bar.className = 'onze-privacy-notice';
    bar.setAttribute('role', 'note');
    bar.innerHTML =
      '<p>Ce site ne dépose aucun cookie de mesure d’audience ni de service tiers. ' +
      'Seuls votre panier et votre taille préférée sont mémorisés sur votre appareil (stockage local), ' +
      'sans transmission à un tiers. <a href="politique-de-confidentialite.html">En savoir plus</a></p>' +
      '<button type="button">Compris</button>';

    document.body.appendChild(bar);

    bar.querySelector('button').addEventListener('click', function () {
      bar.remove();
      try {
        localStorage.setItem(STORAGE_KEY, '1');
      } catch (e) {
        /* stockage indisponible : le bandeau réapparaîtra, sans conséquence */
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
