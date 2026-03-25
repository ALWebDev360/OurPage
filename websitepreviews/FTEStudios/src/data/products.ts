export interface Product {
  id: string;
  title: string;
  subtitle: string;
  price: number;
  currency: string;
  images: string[];
  sizes: { label: string; available: boolean }[];
  badge?: string;
  description: {
    bullets: string[];
    tagline: string;
  };
}

export const products: Product[] = [
  {
    id: "midnight-motion-vol-4",
    title: 'Midnight Motion Vol. 4',
    subtitle: 'The city never sleeps, neither do we.',
    price: 125.0,
    currency: "USD",
    images: [
      "https://ftestudioz.myshopify.com/cdn/shop/files/447DA9F5-CA77-4CC4-AD4A-7E83DE28FCAA.jpg?v=1767939134&width=800",
      "https://ftestudioz.myshopify.com/cdn/shop/files/CA0E4212-CEB4-4E5F-8DFD-A9856D5E943C.jpg?v=1767939134&width=800",
      "https://ftestudioz.myshopify.com/cdn/shop/files/38B0FCC9-58F6-483E-B909-1DE2E0E4D547.jpg?v=1767939134&width=800",
    ],
    sizes: [
      { label: "S", available: false },
      { label: "M", available: false },
      { label: "L", available: true },
      { label: "XL", available: true },
      { label: "2XL", available: true },
    ],
    badge: "New Drop",
    description: {
      bullets: [
        "Full outfit set designed for movement after dark",
        "Clean silhouette, bold presence",
        "Made for late nights, city lights, and focused minds",
        "Effortless fit that moves with confidence",
        "Where style meets momentum",
      ],
      tagline: "Midnight Motion isn't just an outfit — it's a mindset.",
    },
  },
];
