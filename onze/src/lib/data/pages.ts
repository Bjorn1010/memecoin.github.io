/* Editorial content for the help and legal sections. Kept as data rather than
 * eight near-identical page files — one route renders any of them, and the
 * footer links stop 404-ing. Swap for a CMS without touching the routes. */

export interface StaticPage {
  slug: string;
  title: string;
  intro: string;
  sections: { heading: string; body: string[] }[];
}

export const aidePages: StaticPage[] = [
  {
    slug: "livraison",
    title: "Livraison & délais",
    intro: "Toutes les commandes partent de Suisse, flocage déjà appliqué.",
    sections: [
      {
        heading: "Délais de préparation",
        body: [
          "Les commandes sont préparées sous 48 heures ouvrables. Le flocage nom et numéro est appliqué avant l'expédition, ce qui est déjà compté dans ce délai.",
          "Les commandes passées le vendredi après 14 h partent le lundi suivant.",
        ],
      },
      {
        heading: "Délais d'acheminement",
        body: [
          "Suisse : 2 à 4 jours ouvrables. Europe : 4 à 8 jours ouvrables. Reste du monde : 8 à 15 jours ouvrables.",
          "Un numéro de suivi est envoyé par e-mail dès la remise au transporteur.",
        ],
      },
      {
        heading: "Frais",
        body: [
          "Livraison standard offerte dès 120 CHF d'achat. En dessous, elle est facturée au tarif affiché au paiement. L'express 24 h est disponible en supplément.",
        ],
      },
    ],
  },
  {
    slug: "retours",
    title: "Retours & échanges",
    intro: "30 jours pour changer d'avis, sous conditions.",
    sections: [
      {
        heading: "Conditions",
        body: [
          "Vous disposez de 30 jours après réception pour retourner un article non porté, non lavé, avec son étiquette d'origine attachée.",
          "Les maillots personnalisés avec un nom ou un numéro qui ne figure pas au catalogue ne sont pas repris, sauf défaut de fabrication.",
        ],
      },
      {
        heading: "Procédure",
        body: [
          "Écrivez-nous depuis la page contact en indiquant votre numéro de commande. Une étiquette de retour vous est envoyée.",
          "Le remboursement intervient sous 5 à 10 jours ouvrables après réception et contrôle de l'article.",
        ],
      },
    ],
  },
  {
    slug: "tailles",
    title: "Guide des tailles",
    intro: "Les maillots taillent au plus près du corps. En cas de doute, prenez au-dessus.",
    sections: [
      {
        heading: "Adulte",
        body: [
          "S : 88-94 cm de tour de poitrine. M : 96-102 cm. L : 104-110 cm. XL : 112-118 cm. XXL : 120-126 cm.",
          "Ces mesures correspondent au tour de poitrine du porteur, pas au vêtement à plat.",
        ],
      },
      {
        heading: "Enfant",
        body: [
          "Les tailles enfant suivent l'âge : 4A, 6A, 8A, 10A, 12A et 14A. Elles correspondent à des tailles standard européennes.",
        ],
      },
      {
        heading: "Coupe",
        body: [
          "La coupe supporter est plus ample que la coupe joueur. Les kits rétros suivent les coupes de leur époque et taillent généralement plus large.",
        ],
      },
    ],
  },
  {
    slug: "flocage",
    title: "Flocage",
    intro: "Nom, numéro et écusson inclus sur chaque maillot, sans supplément.",
    sections: [
      {
        heading: "Ce qui est inclus",
        body: [
          "Le flocage trois parties — nom, numéro et écusson de compétition — est appliqué à chaud avant expédition et compris dans le prix affiché.",
          "Le nom accepte jusqu'à 12 caractères, le numéro jusqu'à 2 chiffres.",
        ],
      },
      {
        heading: "Entretien",
        body: [
          "Lavez le maillot sur l'envers à 30 °C. Ne repassez jamais directement sur le flocage. Séchage à l'air libre, jamais au sèche-linge.",
        ],
      },
    ],
  },
  {
    slug: "contact",
    title: "Nous contacter",
    intro: "Une question sur une commande, une taille ou un flocage ?",
    sections: [
      {
        heading: "Service client",
        body: [
          "Écrivez à contact@onze.example. Nous répondons sous 24 heures ouvrables, du lundi au vendredi.",
          "Indiquez votre numéro de commande pour toute demande de suivi, de retour ou d'échange.",
        ],
      },
      {
        heading: "Demandes spéciales",
        body: [
          "Un maillot introuvable au catalogue ? Décrivez-nous le club, la saison et le type de kit — nous cherchons pour vous.",
        ],
      },
    ],
  },
];

export const legalPages: StaticPage[] = [
  {
    slug: "cgv",
    title: "Conditions générales de vente",
    intro: "Applicables à toute commande passée sur ONZE.",
    sections: [
      {
        heading: "Produits",
        body: [
          "Les articles vendus sur ce site sont des répliques non officielles. ONZE n'est affilié à aucun club, aucune fédération ni aucun équipementier. Les noms d'équipes et de compétitions sont cités à titre purement descriptif.",
        ],
      },
      {
        heading: "Prix et paiement",
        body: [
          "Les prix sont affichés en francs suisses, TVA de 8,1 % incluse. Le paiement est exigible à la commande.",
        ],
      },
      {
        heading: "Droit applicable",
        body: [
          "Les présentes conditions sont soumises au droit suisse. Tout litige relève des tribunaux compétents du siège du vendeur.",
        ],
      },
    ],
  },
  {
    slug: "confidentialite",
    title: "Confidentialité",
    intro: "Ce que nous collectons, et pourquoi.",
    sections: [
      {
        heading: "Données collectées",
        body: [
          "Nous traitons les informations nécessaires au traitement d'une commande : identité, adresse de livraison, adresse e-mail et historique d'achat.",
          "Les données de carte bancaire ne transitent pas par nos serveurs et sont traitées directement par le prestataire de paiement.",
        ],
      },
      {
        heading: "Vos droits",
        body: [
          "Vous pouvez demander l'accès, la rectification ou la suppression de vos données à tout moment en écrivant à contact@onze.example.",
        ],
      },
    ],
  },
  {
    slug: "mentions",
    title: "Mentions légales",
    intro: "Informations sur l'éditeur du site.",
    sections: [
      {
        heading: "Éditeur",
        body: [
          "ONZE — boutique de démonstration. Ce site est un projet de démonstration et ne traite aucune commande réelle.",
        ],
      },
      {
        heading: "Propriété intellectuelle",
        body: [
          "Aucun logo, écusson, photographie ou marque appartenant à un club, une fédération ou un équipementier n'est reproduit sur ce site. Les visuels de maillots sont générés et n'ont pas de valeur documentaire.",
        ],
      },
    ],
  },
];

export function findPage(collection: StaticPage[], slug: string) {
  return collection.find((p) => p.slug === slug);
}
