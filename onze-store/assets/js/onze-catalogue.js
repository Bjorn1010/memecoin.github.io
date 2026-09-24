// Catalogue produits Onze. Source unique pour la boutique, les fiches produit,
// le panier et la scène 3D de la page d'accueil.

export const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL'];

export const FLOCAGE_PRICE = 12;

export const PRODUCTS = [
  {
    id: 'domicile-noir',
    category: 'domicile',
    name1: 'Domicile',
    name2: 'Noir',
    number: '11',
    price: 79,
    primary: '#161616',
    secondary: '#E11D2E',
    accent: '#F5F5F5',
    pattern: 'sash',
    tasteSecondary: '#FF4D5E',
    tastePrimary: '#3B0A10',
    tagline: 'Le noir intemporel du vestiaire.',
    description:
      "La base de toute collection. Un noir profond traversé d'une écharpe rouge, coupe athlétique et col côtelé. Le maillot qu'on enfile sans réfléchir, du terrain au tribune.",
    details: ['Polyester technique recyclé 160 g/m²', 'Col côtelé rouge', 'Coupe athlétique ajustée', 'Fabriqué en Europe'],
  },
  {
    id: 'exterieur-blanc',
    category: 'exterieur',
    name1: 'Extérieur',
    name2: 'Blanc',
    number: '7',
    price: 79,
    primary: '#F2F2F0',
    secondary: '#0B2545',
    accent: '#0B2545',
    pattern: 'pinstripe',
    tasteSecondary: '#8FD3FF',
    tastePrimary: '#0B2545',
    tagline: "La respiration des soirs d'été.",
    description:
      "Blanc immaculé rehaussé d'un bleu marine profond, fines rayures verticales pour l'allure. Le maillot d'extérieur pensé pour les soirs où il fait encore chaud à 21h.",
    details: ['Polyester technique recyclé 160 g/m²', 'Rayures tissées dans la maille', 'Col V marine', 'Fabriqué en Europe'],
  },
  {
    id: 'third-dore',
    category: 'third',
    name1: 'Third',
    name2: 'Doré',
    number: '9',
    price: 89,
    primary: '#171310',
    secondary: '#C9A24B',
    accent: '#C9A24B',
    pattern: 'gradient',
    tasteSecondary: '#FFD877',
    tastePrimary: '#4A3400',
    tagline: 'Celui qui sort du rang.',
    description:
      "Un or discret qui monte du bas vers le haut sur un fond noir mat. Le troisième maillot, celui qu'on garde pour les soirs de grande occasion.",
    details: ['Polyester technique recyclé 160 g/m²', 'Dégradé imprimé en sublimation', 'Liseré doré aux manches', 'Fabriqué en Europe'],
  },
  {
    id: 'gardien-vert',
    category: 'gardien',
    name1: 'Gardien',
    name2: 'Vert',
    number: '1',
    price: 84,
    primary: '#0F3B26',
    secondary: '#F2F2F2',
    accent: '#6FE3A6',
    pattern: 'blocks',
    tasteSecondary: '#6FE3A6',
    tastePrimary: '#063820',
    tagline: 'Taillé pour les gardiens.',
    description:
      "Un vert profond, une coupe plus ample, des renforts aux coudes. Pensé pour l'amplitude des mouvements et les atterrissages sur terrain sec.",
    details: ['Polyester technique recyclé 180 g/m²', 'Renforts coudes', 'Coupe ample gardien', 'Fabriqué en Europe'],
  },
  {
    id: 'training-gris',
    category: 'training',
    name1: 'Training',
    name2: 'Gris',
    number: '4',
    price: 64,
    primary: '#5B616B',
    secondary: '#111318',
    accent: '#C8CDD6',
    pattern: 'mesh',
    tasteSecondary: '#C8CDD6',
    tastePrimary: '#1F2530',
    tagline: "Le compagnon d'entraînement.",
    description:
      "Gris chiné, maille ouverte sur les flancs, pensé pour l'effort au quotidien. Celui qui prend les séances du mardi soir sans broncher.",
    details: ['Polyester technique recyclé 150 g/m²', 'Panneaux maille aérée', 'Coupe training', 'Fabriqué en Europe'],
  },
  {
    id: 'edition-limitee',
    category: 'edition',
    name1: 'Édition',
    name2: 'Limitée',
    number: '10',
    price: 109,
    primary: '#3D0A1E',
    secondary: '#D4AF37',
    accent: '#FF7FB0',
    pattern: 'stripes',
    tasteSecondary: '#FF7FB0',
    tastePrimary: '#3D0A1E',
    tagline: 'Série numérotée.',
    description:
      "Bordeaux profond, filet doré, numérotée à la main de 1 à 500. Quand c'est parti, c'est parti — on ne relance pas la série.",
    details: ['Polyester technique recyclé 170 g/m²', 'Numérotation manuelle 1 à 500', 'Filet doré tissé', 'Fabriqué en Europe'],
  },
];

export const CATEGORIES = [
  { id: 'domicile', label: 'Domicile' },
  { id: 'exterieur', label: 'Extérieur' },
  { id: 'third', label: 'Third' },
  { id: 'gardien', label: 'Gardien' },
  { id: 'training', label: 'Training' },
  { id: 'edition', label: 'Édition limitée' },
];

export const getProduct = (id) => PRODUCTS.find((p) => p.id === id) || PRODUCTS[0];

/**
 * Le numéro d'origine fait partie du design et reste gratuit. Le flocage n'est
 * facturé que s'il y a un nom, ou un numéro différent de celui du modèle.
 */
export const hasFlocage = (product, { name, number } = {}) => {
  const cleanName = (name ?? '').toString().trim();
  const cleanNumber = (number ?? '').toString().trim();
  if (cleanName) return true;
  return Boolean(cleanNumber) && cleanNumber !== String(product.number);
};

export const formatPrice = (value) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', minimumFractionDigits: 0 }).format(value);
