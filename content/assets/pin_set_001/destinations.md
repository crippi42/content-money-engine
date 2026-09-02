# Pin Set 001 — Pinterest Destination Registry

**Asset ID**: `pin_set_001`
**Channel**: pinterest
**Experiment ID**: `D4-HOSTINGER-PINTEREST-001`
**Content variant**: `setup_guide_v1`
**Affiliate status**: PLACEHOLDER (no affiliate links used in this registry)

---

## Base Production URL

```
https://crippi42.github.io/content-money-engine/content/landing_pages/hostinger-setup-guide-v1.html
```

## UTM Parameters

| Parameter | Value |
|---|---|
| `utm_source` | `pinterest` |
| `utm_medium` | `social` |
| `utm_campaign` | `d4_hostinger_setup` |
| `utm_content` | `pin_01` through `pin_08` (per pin) |

## Pin Destinations

| # | Pin File | Anchor | Destination URL |
|---|---|---|---|
| 1 | `pin_01.png` / `pin_01.svg` | `#step-1-purpose` | `https://crippi42.github.io/content-money-engine/content/landing_pages/hostinger-setup-guide-v1.html?utm_source=pinterest&utm_medium=social&utm_campaign=d4_hostinger_setup&utm_content=pin_01#step-1-purpose` |
| 2 | `pin_02.png` / `pin_02.svg` | `#step-2-domain` | `https://crippi42.github.io/content-money-engine/content/landing_pages/hostinger-setup-guide-v1.html?utm_source=pinterest&utm_medium=social&utm_campaign=d4_hostinger_setup&utm_content=pin_02#step-2-domain` |
| 3 | `pin_03.png` / `pin_03.svg` | `#step-3-plan` | `https://crippi42.github.io/content-money-engine/content/landing_pages/hostinger-setup-guide-v1.html?utm_source=pinterest&utm_medium=social&utm_campaign=d4_hostinger_setup&utm_content=pin_03#step-3-plan` |
| 4 | `pin_04.png` / `pin_04.svg` | `#step-4-payment` | `https://crippi42.github.io/content-money-engine/content/landing_pages/hostinger-setup-guide-v1.html?utm_source=pinterest&utm_medium=social&utm_campaign=d4_hostinger_setup&utm_content=pin_04#step-4-payment` |
| 5 | `pin_05.png` / `pin_05.svg` | `#step-5-domain-connect` | `https://crippi42.github.io/content-money-engine/content/landing_pages/hostinger-setup-guide-v1.html?utm_source=pinterest&utm_medium=social&utm_campaign=d4_hostinger_setup&utm_content=pin_05#step-5-domain-connect` |
| 6 | `pin_06.png` / `pin_06.svg` | `#step-6-wordpress` | `https://crippi42.github.io/content-money-engine/content/landing_pages/hostinger-setup-guide-v1.html?utm_source=pinterest&utm_medium=social&utm_campaign=d4_hostinger_setup&utm_content=pin_06#step-6-wordpress` |
| 7 | `pin_07.png` / `pin_07.svg` | `#step-7-config` | `https://crippi42.github.io/content-money-engine/content/landing_pages/hostinger-setup-guide-v1.html?utm_source=pinterest&utm_medium=social&utm_campaign=d4_hostinger_setup&utm_content=pin_07#step-7-config` |
| 8 | `pin_08.png` / `pin_08.svg` | `#step-8-launch` | `https://crippi42.github.io/content-money-engine/content/landing_pages/hostinger-setup-guide-v1.html?utm_source=pinterest&utm_medium=social&utm_campaign=d4_hostinger_setup&utm_content=pin_08#step-8-launch` |

## Notes

* All URLs place query parameters (`?utm_...`) BEFORE the fragment (`#step-...`), per RFC 3986.
* All 8 anchors exactly match `<h2 id="...">` elements in the canonical landing page.
* `utm_content` value matches the pin number for each row.
* No `AFFILIATE_LINK_PENDING` placeholders; affiliate links are not used in this registry.
* This file is a version-controlled source of truth for the 8 pin destination URLs.
* Pin image files (PNG/SVG) are not modified; destinations are set at publish time in the Pinterest UI by copying the URL from this registry.
