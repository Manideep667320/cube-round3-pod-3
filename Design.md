# Medha --- E-commerce UI Design Specification

> **Source:** User-provided UI design screenshot.\
> **Design direction:** Premium editorial commerce --- warm, minimal,
> lifestyle-led, with a restrained luxury palette and product
> photography/3D imagery.\
> **Note:** Color values below are close visual estimates sampled by eye
> from the screenshot, not verified source design tokens.

## 1. Visual Direction

Medha presents a broad product catalogue through a premium
lifestyle-shopping experience. The visual language combines:

-   Warm ivory backgrounds instead of stark white.
-   Near-black typography with a high-contrast editorial serif for large
    headlines.
-   Neutral sans-serif typography for navigation, labels, prices, and
    controls.
-   Muted champagne-gold accents used sparingly.
-   Large, softly lit product imagery with floating/arranged objects in
    the hero.
-   Rounded white category and product surfaces, subtle borders, and
    minimal shadows.
-   A dark promotional banner at the bottom to create contrast and a
    second visual focal point.

The design should feel calm, curated, premium, and approachable. Avoid
strong gradients, loud saturated colors, heavy shadows, excessive card
decoration, and dense borders.

## 2. Color Scheme

### Core palette

  --------------------------------------------------------------------------
  Token                      Suggested HEX           Usage
  -------------------------- ----------------------- -----------------------
  `color.canvas`             `#F7F3ED`               Main warm ivory page
                                                     background

  `color.surface`            `#FFFCF8`               Product cards, category
                                                     rail, search surface

  `color.surface-soft`       `#F1EBE3`               Secondary sections and
                                                     subtle card contrast

  `color.text-primary`       `#191714`               Main headings,
                                                     navigation, product
                                                     names

  `color.text-secondary`     `#6F675F`               Supporting copy,
                                                     descriptions, secondary
                                                     labels

  `color.text-muted`         `#9A9187`               Metadata, inactive
                                                     controls, helper text

  `color.border`             `#E7DED3`               Hairline dividers and
                                                     card borders

  `color.accent-gold`        `#B78A59`               Small highlights,
                                                     active details,
                                                     decorative accent

  `color.accent-gold-soft`   `#E8D3B8`               Soft highlight surfaces
                                                     and subtle emphasis

  `color.dark-surface`       `#201D1A`               Bottom promotional
                                                     banner and dark
                                                     contrast areas

  `color.dark-text`          `#FBF7F0`               Text on dark surfaces

  `color.success`            `#68815D`               Optional positive
                                                     states, such as
                                                     verified or available

  `color.sale`               `#B34E3D`               Optional restrained
                                                     sale/discount state
  --------------------------------------------------------------------------

### Palette usage rules

-   Use warm ivory for most page backgrounds; do not use pure white as
    the dominant canvas.
-   Keep primary text nearly black, not absolute black.
-   Use gold as a **small accent**, not as a large background or primary
    button fill everywhere.
-   Keep borders low-contrast and thin.
-   Reserve the dark surface for one or two high-impact areas, such as
    the bottom promotional banner.
-   Product photography should provide most of the color in the page. UI
    chrome should remain neutral.
-   Success and sale colors are optional semantic tokens; they are not
    dominant colors in the screenshot.

### Suggested CSS variables

``` css
:root {
  --color-canvas: #F7F3ED;
  --color-surface: #FFFCF8;
  --color-surface-soft: #F1EBE3;
  --color-text-primary: #191714;
  --color-text-secondary: #6F675F;
  --color-text-muted: #9A9187;
  --color-border: #E7DED3;
  --color-accent-gold: #B78A59;
  --color-accent-gold-soft: #E8D3B8;
  --color-dark-surface: #201D1A;
  --color-dark-text: #FBF7F0;
  --color-success: #68815D;
  --color-sale: #B34E3D;
}
```

## 3. Typography

### Type system

The screenshot uses an editorial display serif for the hero and selected
section headings, paired with a clean sans-serif for interface elements.

  -----------------------------------------------------------------------
  Role                    Style                   Suggested font options
  ----------------------- ----------------------- -----------------------
  Hero heading            High-contrast editorial `DM Serif Display`,
                          serif, tight            `Playfair Display`,
                          line-height             `Cormorant Garamond`

  Section headings        Serif, medium weight    Same display serif
                                                  family

  Wordmark                Elegant serif or        A restrained serif
                          refined custom wordmark treatment

  Navigation              Neutral sans-serif,     `Inter`, `Manrope`,
                          small and medium weight `DM Sans`

  Body copy               Sans-serif, regular     `Inter`, `Manrope`,
                                                  `DM Sans`

  Product names           Sans-serif, medium      `Inter`, `Manrope`

  Prices and metadata     Sans-serif,             `Inter`, `Manrope`
                          medium/semibold         

  Micro-labels            Sans-serif, uppercase,  `Inter`, `Manrope`
                          letter-spaced           
  -----------------------------------------------------------------------

These are suggested substitutes; the screenshot does not reveal the
exact font files.

### Type scale

Use a responsive scale similar to:

-   Hero heading: `clamp(2.5rem, 4.5vw, 4.75rem)`, line-height
    `0.92–1.0`.
-   Section heading: `1.5–2rem`, line-height `1.05–1.15`.
-   Product title: `0.8–0.95rem`.
-   Body copy: `0.85–1rem`, line-height `1.45–1.6`.
-   Navigation and metadata: `0.7–0.8rem`.
-   Micro-labels: `0.55–0.65rem`, uppercase with increased letter
    spacing.

Keep hero text on short lines. The serif headline should be the most
expressive typographic element; all supporting interface text should be
quiet and highly legible.

## 4. Page Structure

The page is organized into five major horizontal sections.

``` text
NEXA PAGE
├── 1. Header / Primary Navigation
├── 2. Hero / Editorial Product Showcase
├── 3. Shop by Category
├── 4. Featured Products
└── 5. Promotional Experience Banner
```

### 4.1 Header / Primary Navigation

**Purpose:** Brand recognition and fast access to catalogue, search, and
shopping actions.

**Structure:** - Left: `NEXA` wordmark. - Center: category navigation
--- All, Fashion, Electronics, Home & Living, Beauty, Sports, Books,
More. - Right: compact search field, wishlist icon, account icon,
shopping bag/cart icon. - A fine bottom divider separates the header
from the hero.

**Styling:** - Background: `--color-canvas` or `--color-surface`. -
Header height: approximately 64--76 px on desktop. - Horizontal padding:
5--6vw on wide screens. - Navigation labels: small sans-serif, medium
weight, dark neutral. - Icons: thin stroke, consistent 16--20 px size. -
Search: pill-shaped or softly rounded, pale surface, subtle border. -
Keep the header low-profile so the hero remains dominant.

**Responsive behavior:** - On tablet, reduce the number of visible
navigation links and retain search/cart. - On mobile, use wordmark,
search icon, and cart/menu controls; move category links into a drawer
or horizontal scroll area.

### 4.2 Hero / Editorial Product Showcase

**Purpose:** Communicate discovery and premium product variety
immediately.

**Desktop layout:** - Full-width hero with two visual zones. - Left
content block: small uppercase eyebrow, large serif headline, short
supporting paragraph, primary CTA, secondary CTA, and compact
social-proof row. - Right/main visual: large studio-lit product
composition with floating or suspended objects. - Right edge: minimal
vertical slide indicators. - Background blends warm ivory with soft
light and product shadows.

**Content hierarchy:** 1. Eyebrow: "DISCOVER · SHOP · BE INSPIRED" 2.
Headline: "Everything You Love In One Place" 3. One short sentence
describing the catalogue and personalized discovery. 4. Primary CTA:
"Shop Now" 5. Optional customer avatars and compact social proof. 6.
Large product artwork: headphones, sneaker, watch, handbag, fragrance,
camera, lamp, and other category cues. 7. Small "New Arrivals / Up to
40% Off" callout floating near the artwork.

**Styling:** - Hero height: approximately 420--560 px on desktop,
depending on viewport. - Use a 40/60 or 42/58 text-to-visual split. -
Headline should be large, serif, tight, and left-aligned. - The product
scene should feel like a luxury editorial campaign, with realistic
contact shadows and soft warm lighting. - CTA: near-black fill, white
text, pill radius; use gold sparingly for hover/focus details. -
Secondary callout: light surface with a thin border and soft shadow. -
Avoid putting text directly over visually busy products.

**Motion direction, if animated:** - Use very slow floating/parallax
movement for selected objects. - Keep movement subtle and staggered
rather than making every object move. - Respect reduced-motion
preferences. - The hero copy and buttons should remain fixed and
readable while the artwork moves independently.

### 4.3 Shop by Category

**Purpose:** Offer a fast visual entry point into major catalogue
departments.

**Structure:** - A horizontal, rounded, light surface overlapping or
sitting immediately below the hero. - Left-aligned heading: "Shop By
Category." - Category items displayed in one horizontal row. - Each item
includes a small circular or softly rounded product thumbnail, plus a
compact label. - A right-arrow control indicates additional categories.

**Visible categories in the reference:** - Fashion - Electronics - Home
& Living - Beauty - Sports - Books - Toys & Games - Groceries -
Accessories

**Styling:** - Surface: `--color-surface`. - Border: optional 1 px
`--color-border`. - Radius: 18--24 px. - Category image: approximately
34--48 px, with consistent crop and background treatment. - Labels:
small sans-serif, dark neutral. - Active/hover state: subtle warm
surface tint or fine gold outline; avoid loud colored pills.

**Responsive behavior:** - Desktop: one horizontal row. - Mobile:
horizontally scrollable rail with snap alignment. - Ensure focusable
arrow controls and keyboard access.

### 4.4 Featured Products

**Purpose:** Turn discovery into product exploration and shopping
actions.

**Structure:** - Left: serif section heading "Featured Products" with a
short supporting line. - Right/top: filter tabs such as All, Trending,
Best Sellers, New Arrivals, plus compact previous/next controls. -
Below: horizontal row or responsive grid of product cards. - Each card
includes product image, wishlist icon, product name, price, rating, and
compact add-to-cart control.

**Product examples visible in the reference:** - Urban Sneakers -
Classic Watch - Floral Perfume - Modern Sofa - Wireless Headphones -
Coffee Maker

**Card styling:** - Surface: `--color-surface`. - Radius: 10--14 px. -
Border: minimal or none; use spacing and image backgrounds to define
card boundaries. - Product image region: warm neutral studio background,
consistent aspect ratio. - Product name: small, medium-weight
sans-serif. - Price: slightly stronger weight than metadata. - Rating:
small star icon with compact score. - Wishlist: small outlined heart
near the upper-right of the image. - Add-to-cart: small dark circular or
pill control near the bottom-right. - Use consistent card heights and
image crops.

**Layout:** - Desktop: six cards across at the reference's wide layout;
use fewer columns at narrower breakpoints. - Tablet: three cards per row
or a horizontal carousel. - Mobile: two-column grid or horizontally
scrolling cards, depending on content width.

### 4.5 Promotional Experience Banner

**Purpose:** Introduce the personalized-shopping concept and visually
close the first screen.

**Structure:** - Full-width dark banner with rounded corners. - Left:
serif heading "A Smarter Shopping Experience" and one or two lines of
supporting copy. - Center/right: three concise steps with icons: 1.
Browse --- Explore your interests. 2. Get Recommendations ---
Personalized just for you. 3. Shop with Ease --- Add to cart and
checkout. - Right side: lifestyle/product image featuring a mobile phone
and shopping content. - Thin arrows connect the three steps.

**Styling:** - Background: `--color-dark-surface`. - Text:
`--color-dark-text`. - Supporting text: softened warm grey. - Icons and
dividers: muted champagne or low-contrast light grey. - Radius: 18--24
px. - Use photographic imagery that blends into the dark background
rather than placing it in a separate white card. - Keep this section
visually rich but less prominent than the hero.

## 5. Spacing, Grid, and Shape

### Layout system

-   Use a centered responsive content container with a maximum width
    around 1440 px.
-   Desktop side padding: `clamp(24px, 5vw, 80px)`.
-   Main section gaps: 20--32 px.
-   Product-card gaps: 12--18 px.
-   Header and content align to a shared horizontal grid.
-   Use a 12-column grid for the hero and major sections where helpful.

### Spacing tokens

``` css
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
  --space-7: 48px;
  --space-8: 64px;
  --radius-sm: 8px;
  --radius-card: 12px;
  --radius-panel: 20px;
  --radius-pill: 999px;
}
```

### Shape language

-   Buttons: pill-shaped or fully rounded.
-   Category rail: large rounded container.
-   Product cards: restrained 10--14 px corners.
-   Promotional banner: 18--24 px corners.
-   Inputs: softly rounded, thin neutral border.
-   Avoid mixing many unrelated corner radii.

## 6. Imagery and Art Direction

Imagery is a core part of the identity and should carry more visual
weight than decorative UI.

-   Use studio-lit product photography or high-quality 3D product
    renders.
-   Hero objects should appear suspended or arranged in a carefully
    balanced composition, with believable lighting and shadows.
-   Maintain a warm, neutral environment so products stand out
    naturally.
-   Product cards should use consistent camera angle, scale, crop, and
    lighting.
-   Use real category-relevant assets rather than generic abstract
    illustrations.
-   Avoid excessive glassmorphism, glowing borders, random floating UI
    cards, and generic gradient blobs.
-   The image composition should have a clear quiet zone for hero copy.

## 7. Interaction and States

-   Header category links navigate to their corresponding catalogue
    views.
-   Search supports focus, query entry, and clear feedback.
-   Wishlist icons show a clear selected/unselected state.
-   Product cards open product details; add-to-cart controls provide a
    visible confirmation.
-   Category rail scrolls horizontally when content exceeds available
    width.
-   Featured-product tabs visibly identify the selected filter.
-   Carousel arrows update the visible products.
-   Buttons have hover, focus, active, and disabled states.
-   Use subtle transitions around 150--250 ms; avoid springy or
    excessive motion.
-   Keyboard focus must remain visible, using a restrained but clear
    accent outline.

## 8. Responsive Behavior

### Desktop: 1200 px and above

-   Full navigation visible.
-   Hero uses two-column layout with large product artwork.
-   Featured products use a wide multi-column row.
-   Promotional banner displays its steps horizontally.

### Tablet: 768--1199 px

-   Reduce navigation spacing and hero headline size.
-   Keep the hero visual dominant but reduce the number of floating
    objects if necessary.
-   Use three or four product cards per visible row.
-   Allow category rail to scroll horizontally.

### Mobile: below 768 px

-   Compact header with menu/search/cart controls.
-   Stack hero copy and artwork, or place the artwork beneath the
    headline.
-   Keep CTA buttons easy to tap.
-   Make category rail horizontally scrollable.
-   Use two product columns where readable; do not shrink product labels
    to fit six columns.
-   Convert promotional steps into a vertical list or horizontal scroll.
-   Maintain a minimum 44 × 44 px touch target for important controls.
-   Avoid fixed-width desktop compositions that overflow the viewport.

## 9. Accessibility and Quality Requirements

-   Maintain readable contrast between text and warm surfaces.
-   Do not use color alone to communicate availability, selection, or
    errors.
-   Provide descriptive alternative text for meaningful product images.
-   Use semantic headings in the order `h1`, `h2`, `h3`.
-   Make navigation, tabs, carousel controls, wishlist, and cart
    keyboard-accessible.
-   Respect `prefers-reduced-motion`.
-   Keep labels and controls legible at mobile sizes.
-   Use optimized responsive images and lazy-load below-the-fold product
    imagery.

## 10. Suggested Component Architecture

``` text
NexaHomePage
├── SiteHeader
│   ├── BrandWordmark
│   ├── PrimaryNavigation
│   ├── SearchField
│   └── HeaderActions
├── HeroShowcase
│   ├── HeroCopy
│   ├── HeroActions
│   ├── SocialProof
│   ├── FloatingProductComposition
│   ├── OfferCallout
│   └── HeroPagination
├── CategoryRail
│   ├── CategoryItem × N
│   └── CategoryRailControls
├── FeaturedProducts
│   ├── SectionHeading
│   ├── ProductFilters
│   ├── ProductCard × N
│   └── CarouselControls
└── ShoppingExperienceBanner
    ├── BannerCopy
    ├── ShoppingStep × 3
    └── LifestyleImage
```

## 11. Design Acceptance Checklist

-   [ ] Warm ivory background is dominant.
-   [ ] Serif display type is used for the hero and section headings.
-   [ ] Interface labels use a clean sans-serif.
-   [ ] Gold is used as a restrained accent, not a dominant color.
-   [ ] Header is compact and aligned to the page grid.
-   [ ] Hero has clear text/artwork separation.
-   [ ] Product artwork has realistic lighting and consistent visual
    quality.
-   [ ] Category rail feels lightweight and easy to scan.
-   [ ] Product cards have consistent image treatment and compact
    metadata.
-   [ ] Dark promotional banner creates contrast without overpowering
    the page.
-   [ ] Responsive layouts do not simply scale down the desktop layout.
-   [ ] Interactive states, keyboard focus, and reduced-motion behavior
    are implemented.
-   [ ] Final implementation uses real product assets and real
    interaction states rather than static mock-only elements.

------------------------------------------------------------------------

**Implementation note:** This document translates the supplied
screenshot into a practical design specification. The exact original
font family, source hex values, grid measurements, and interaction
behavior cannot be confirmed from the screenshot alone; treat the
proposed values as a coherent implementation baseline and tune them
against the final assets and viewport.
