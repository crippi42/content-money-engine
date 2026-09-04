# Phase D7 — Controlled Publishing Setup

**Date**: 2026-09-01  
**Phase**: Preparation / Planning  
**Status**: COMPLETE  
**Objective**: Prepare everything required for the first controlled live experiment, but DO NOT publish anything yet.

---

## Experiment Identity

Preserved from D4/D5/D6:

| Field | Value |
|---|---|
| experiment_id | `D4-HOSTINGER-PINTEREST-001` |
| asset_id | `pin_set_001` |
| channel | `pinterest` |
| content_variant | `setup_guide_v1` |
| destination | `/hostinger-setup-guide-v1.html` |

**Verbatim preservation confirmed** in all D4 asset metadata (landing page HTML comments, pin_set_001/readme.md, pin_set_001/pin_templates.md tracking metadata section). No new experiment ID created.

---

## 1. Final Asset Inventory

### Production candidate assets (all local, none published)

| Asset | File Path | Status | Last Modified |
|---|---|---|---|
| Landing page | `content/landing_pages/hostinger-setup-guide-v1.html` | DRAFT — placeholders present, not published | 2026-09-01 16:21 |
| Infographic master | `content/assets/pin_set_001/infographic_master.svg` | DRAFT — SVG valid, not rendered/published | 2026-09-01 16:21 |
| Pin templates spec | `content/assets/pin_set_001/pin_templates.md` | DRAFT — 8 pin specs documented, not rendered | 2026-09-01 16:20 |
| Pin set readme/metadata | `content/assets/pin_set_001/readme.md` | DRAFT — metadata present, not published | 2026-09-01 16:21 |

### Supporting research assets

| Asset | File Path | Status |
|---|---|---|
| D1 — Affiliate opportunity research | `memory/research/phase_d1_affiliate_opportunity_research.md` | COMPLETE (historical; contains D2 corrections) |
| D2 — Hostinger validation | `memory/research/phase_d2_hostinger_validation.md` | COMPLETE (verified factual source) |
| D3 — First dollar strategy | `memory/research/phase_d3_first_dollar_strategy.md` | COMPLETE (publishing strategy source) |
| D5 — Paid task revenue research | `memory/research/phase_d5_paid_task_revenue_research.md` | COMPLETE (secondary path, not used in first experiment) |
| D6 — Human asset review | `memory/research/phase_d6_human_asset_review.md` | COMPLETE (audit of D4 assets) |
| D6.1 — Publication blocker fixes | `memory/research/phase_d6_1_blocker_fixes.md` | COMPLETE (all 3 blockers fixed) |
| D6.2 — Plan name alignment | `memory/research/phase_d6_2_plan_alignment.md` | COMPLETE (plan names aligned) |

### D4 asset status summary

**Landing page** (`hostinger-setup-guide-v1.html`):
- 345 lines, valid HTML5
- HTML comments on lines 108-113 contain experiment tracking metadata:
  - `<!-- experiment_id: D4-HOSTINGER-PINTEREST-001 -->`
  - `<!-- asset_id: landing_page_001 -->`
  - `<!-- channel: pinterest_plus_seo -->`
  - `<!-- content_variant: setup_guide_v1 -->`
  - `<!-- destination: /hostinger-setup-guide -->`
- **3 affiliate placeholder blocks** (lines 119-121, 221-223, 319-321) with `AFFILIATE_LINK_PENDING` marker
- FTC disclosure present (line 116) in header disclosure `div`
- Pricing table (lines 131-160) corrected to verified Hostinger pricing
- Plan names aligned: Premium ($2.99/mo), Unlimited ($3.99/mo), Cloud Startup ($7.99/mo)

**Infographic master** (`infographic_master.svg`):
- 91 lines, valid SVG (opening `<svg` and closing `</svg>` both present)
- Dimensions: 1000 × 1500 px (2:3 Pinterest standard)
- 8 steps with purple accent (#5a3de6)
- Pricing in Step 3 (lines 31-33): Premium $2.99/mo, Unlimited $3.99/mo, Cloud Startup $7.99/mo
- AFFILIATE_LINK_PENDING footer text on line 89
- Not yet rendered to PNG for Pinterest upload

**Pin templates** (`pin_templates.md`):
- 8 pin specifications, each with title, subtitle, visual elements, CTA, footer
- Tracking metadata table (lines 159-171): pin #, topic, CTA, destination anchor
- UTM parameters documented: `utm_source=pinterest`, `utm_medium=social`, `utm_campaign=d4_hostinger_setup`, `utm_content=pin_01` through `pin_08`
- Destination anchors: `#step-1-purpose` through `#step-8-launch`

**Readme** (`pin_set_001/readme.md`):
- Asset metadata table (experiment_id, asset_id, content_variant, destination, affiliate_status)
- ASCII diagram of infographic layout (lines 28-106)
- Color palette, typography specifications
- Three affiliate placeholder locations documented (lines 213-225)
- Content quality notes (lines 227-235): no earnings claims, no fake testimonials, prices verified

**Destination URL discrepancy** (documented, not blocking):
- Landing page HTML metadata comment says: `/hostinger-setup-guide`
- Pin set readme says: `/content/landing_pages/hostinger-setup-guide-v1.html`
- Both refer to the same file. The canonical published URL should be standardized to one path.

---

## 2. Affiliate-Link Insertion Plan

### Current state: `AFFILIATE_LINK_PENDING` placeholders (NOT to be replaced yet)

The landing page contains **3 placeholder blocks**, each wrapped in a `div` with class `affiliate-placeholder`:

| # | HTML Location | Context | Planned Affiliate Link Destination |
|---|---|---|---|
| 1 | Line 119-121 (after disclosure, before Step 1) | Top-of-page primary CTA | Hostinger "Websites" hosting signup page with Impact aff sub-ID for primary funnel |
| 2 | Line 221-223 (after Step 3 "Plan Comparison") | Mid-content CTA after plan selection | Hostinger plan signup page with Impact aff sub-ID for "plan-recommendation" funnel |
| 3 | Line 319-321 (after Step 8 "Launch & Verify") | Bottom CTA after tutorial completion | Hostinger "Websites" hosting signup page with Impact aff sub-ID for "completed-guide" funnel |

### Planned link destinations (per D2 verified Hostinger affiliate structure)

**Platform**: Impact Radius (`partners.hostinger.com`) — Hostinger's official affiliate platform.

**Primary link target**: Hostinger "Websites" hosting category page (entry-level shared hosting landing page on hostinger.com), carrying the affiliate tracking parameters:
- Impact `sub1` parameter: campaign identifier (`d4_hostinger_setup`)
- Impact `sub2` parameter: pin identifier (`pin_01` through `pin_08`)
- Impact `sub3` parameter: funnel stage (`top`, `mid`, `bottom`)

**Expected tracking parameters** (to be appended after affiliate link approval):

```
?utm_source=pinterest
&utm_medium=social
&utm_campaign=d4_hostinger_setup
&utm_content=pin_01  (varies per pin)
&af_sub1=top         (funnel stage for placeholder #1)
&af_sub1=mid         (funnel stage for placeholder #2)
&af_sub1=bottom      (funnel stage for placeholder #3)
```

### Hostinger tracking/sub-ID mechanism

**Source**: D2 research, verified from `https://www.hostinger.com/affiliates/faqs` (accessed 2026-09-01).

| Property | Value |
|---|---|
| Affiliate platform | Impact Radius (impact.com) |
| Cookie duration | 30 days |
| Commission rate | Flat 40% of initial purchase (NOT tiered — corrected from D1) |
| Commissionable plans | Web Hosting packages (Premium, Unlimited, Cloud Startup) |
| NOT commissionable | 1-month plans, renewals, upgrades |
| Minimum payout | $100 (PayPal) or $500 (bank transfer) + 3 approved conversions |
| Clearing period | 45 days before commissions are paid |
| Refund risk | Commission revoked if customer cancels within 30-day money-back guarantee |

Impact Radius supports `sub1`, `sub2`, `sub3` sub-ID fields for tracking campaign, content, and funnel stage. These are appended to the affiliate tracking link as URL parameters.

### What must be verified before insertion

| # | Verification Step | Responsible | Must Be Complete Before |
|---|---|---|---|
| 1 | Hostinger affiliate application approved via Impact Radius | Omar (manual) | Inserting any real link |
| 2 | Obtain actual affiliate tracking link from Impact dashboard | Omar (manual) | Link insertion |
| 3 | Verify link destinations resolve to correct Hostinger plan pages | Omar (manual click test) | Go-live |
| 4 | Verify Impact sub-ID parameters are correctly formatted | Omar (Impact support) | Go-live |
| 5 | Confirm Impact tracking pixel loads on destination pages | Omar (browser dev tools) | Go-live |
| 6 | Test full funnel click path (pin → landing page → Hostinger) | Omar (manual) | Go-live |
| 7 | Verify UTM parameters do not break affiliate cookie tracking | Omar (test click + cookie check) | Go-live |

### Insertion method (planned)

When approved, each `affiliate-placeholder` div will be replaced with an actual `<a>` tag:

```html
<a href="https://www.hostinger.com/[affiliate-link]?sub1=d4_hostinger_setup&sub2=pin_01&sub3=top" 
   target="_blank" 
   rel="nofollow noopener noreferrer">
  Sign up for Hostinger — Get the 8-step setup guide plus exclusive pricing
</a>
```

The three existing CSS classes for `.affiliate-placeholder` already define a visually distinct red-dashed block that clearly signals "this is an affiliate link."

---

## 3. Publishing Plan

### Landing-page publishing destination

**Proposed**: GitHub Pages (free, no account creation required, no spending).

| Option | Path | Reasoning |
|---|---|---|
| GitHub Pages | `https://[username].github.io/content-money-engine/hostinger-setup-guide-v1.html` | Free, no credit card, no hosting account, version-controlled alongside source. **RECOMMENDED for first experiment.** |
| Local file only | `content/landing_pages/hostinger-setup-guide-v1.html` served via `python -m http.server` | Zero cost, but no public URL. Pinterest cannot link to localhost. |
| Notion page | Copy-paste HTML into a Notion page | Free, public URL possible, but loses HTML fidelity and UTM tracking. |
| Netlify/Vercel | Free tier static hosting | Free, public URL, but requires account creation (email + provider auth). |

**Recommendation**: GitHub Pages is the smallest-first publishing destination. It provides a public HTTPS URL at zero cost with no external account beyond an existing GitHub account (which Omar already has).

**Canonical URL** (proposed): `https://[username].github.io/content-money-engine/hostinger-setup-guide-v1.html`

All UTM parameters and the destination should reference this canonical URL. The HTML metadata comment on line 113 currently says `/hostinger-setup-guide` — this should be updated to the canonical full URL before go-live.

### Pinterest publishing sequence

**Pin 1 (first to publish)**: "Step 1 — Choose Your Website Purpose"
- **Title**: "What Kind of Website Do You Need? (Pick the Right Plan)"
- **Rationale**: Broadest appeal, highest search volume, introduces the 8-step concept. Serves as the umbrella pin that drives to the landing page.

**Sequence**: Pins 1 through 8, published in order, **one pin every 3 days**.

| Pin # | Publish Day (relative to Pin 1) | Topic |
|---|---|---|
| 1 | Day 0 | Choose Your Website Purpose |
| 2 | Day 3 | Choose Your Domain |
| 3 | Day 6 | Compare Hosting Plans |
| 4 | Day 9 | Complete Setup |
| 5 | Day 12 | Connect Your Domain |
| 6 | Day 15 | Install WordPress |
| 7 | Day 18 | Configure Essentials |
| 8 | Day 21 | Launch & Verify |

**Spacing rationale**: 3 days between pins allows each pin to gain initial impressions before the next one dilutes attention. This is conservative for a first experiment — faster spacing (1 pin/day) could be tested after validating that pins 1 and 2 drive clicks.

**Pin rendering requirement**: The SVG infographic and `pin_templates.md` specs are currently text-based descriptions and SVG markup. Before publishing, **each of the 8 pins must be rendered as a PNG image** (1000 × 1500 px). The SVG can be exported to PNG, and the pin_templates.md specs can guide the creation of the remaining 7 individual pin designs from the master infographic.

**Board**: Create or use an existing "Web Hosting Tutorials" or "Beginner Website Setup" board on Pinterest.

### Experiment duration

**Minimum**: 30 days of active data collection.

**Rationale**: Pinterest's algorithm typically needs 7-14 days to learn which audience finds a pin relevant. 30 days ensures:
- The 8-pin sequence has been live for at least 9 days
- Each pin has had at least one full week to accumulate impressions
- Initial conversion funnel data (impressions → clicks → visits → actions) can be observed

**Extended**: Up to 60 days if early results are inconclusive (low impressions or no clicks).

### What constitutes a meaningful result

| Metric | Meaningful Threshold (30-day minimum) |
|---|---|
| Pinterest impressions (8 pins combined) | ≥ 5,000 total |
| Pin clicks (to landing page) | ≥ 25 total (0.5% minimum CTR) |
| Landing page visits (with UTM params) | ≥ 20 unique |
| Hostinger referral clicks (from landing page) | ≥ 5 total |
| Hostinger sign-ups | ≥ 1 conversion |
| Commission earned | ≥ $50 (1 sale of 48-month plan at 40% of $143.52 = $57.41) |

**Interpretation**:
- **Success**: ≥ 1 conversion / ≥ $50 commission within 30 days → validates the funnel direction, proceed to optimize and scale.
- **Neutral**: 0 conversions but ≥ 25 landing page visits and ≥ 5 referral clicks → funnel works, conversion needs optimization (better placement, clearer CTA, different plan emphasis).
- **Failure**: < 25 landing page visits OR < 5 referral clicks → revisit pin design, landing page CTA, or Pinterest audience targeting before spending more effort.

---

## 4. Measurement Plan

### Full funnel

```
Pinterest impressions
        ↓ (CTR)
Pin clicks (to landing page)
        ↓ (landing page CVR)
Landing-page visits
        ↓ (affiliate CTA CTR)
Affiliate clicks (to Hostinger)
        ↓ (Hostinger conversion rate)
Hostinger conversions (sign-ups)
        ↓ (commission)
Commission earned
```

### Metrics available at each stage

| Stage | Metric | Measurable Now? | Source / Method |
|---|---|---|---|
| 1 | Pinterest impressions | ❌ No — requires Pinterest account + published pins | Pinterest Analytics (native) |
| 2 | Pin clicks (to landing page) | ❌ No — requires published pins | Pinterest Analytics (native) |
| 3 | Landing-page visits | ✅ YES — can measure with free analytics on published page | Google Analytics 4 / Plausible / Umami (free self-hosted) |
| 4 | Affiliate clicks (to Hostinger) | ❌ No — requires real affiliate links, not placeholders | Impact Radius dashboard + GA4 event tracking on outbound clicks |
| 5 | Hostinger conversions (sign-ups) | ❌ No — requires Impact Radius access post-approval | Impact Radius dashboard ("Approved Conversions" count) |
| 6 | Commission earned | ❌ No — requires approval + 45-day clearing period | Impact Radius dashboard ("Earnings") |

### Measurable now

- **Landing Page → Affiliate Click CTR**: Can be measured once the landing page is published with a real affiliate link. Set up GA4 outbound click event tracking on the affiliate `<a>` tag.
- **Landing Page → Hostinger Referral**: GA4 can track outbound clicks to `hostinger.com` with UTM parameters.
- **Landing Page bounce rate / time on page**: GA4 or Plausible (free) can measure engagement.
- **Pin design quality**: Can be pre-tested by rendering the SVG/pin templates and getting human visual feedback before publishing.

### Requires affiliate/publishing access

- **Pinterest impressions & clicks**: Requires active Pinterest business account + published pins.
- **Impact Radius conversion data**: Requires approved Hostinger affiliate account + 45-day clearing period.
- **Pinterest Analytics**: Requires Pinterest business account (separate from personal account).

### Measurement tooling plan (all free)

| Tool | Purpose | Cost | Access Required At |
|---|---|---|---|
| Google Analytics 4 | Landing page visits, outbound click tracking, UTM attribution | Free | Landing page published |
| Google Search Console | SEO performance, discovery keywords | Free | Landing page published + verified ownership |
| Pinterest Analytics | Pin impressions, clicks, saves | Free (business account) | Pinterest business account |
| Impact Radius dashboard | Conversions, commission, sub-ID reporting | Included with affiliate approval | Hostinger affiliate approved |
| UTM.io or manual spreadsheet | UTM parameter management and attribution | Free / Manual | Pre-publish (planning) |

### UTM parameter specification (from D4 assets, documented in pin_templates.md)

```
utm_source=pinterest
utm_medium=social
utm_campaign=d4_hostinger_setup
utm_content=pin_01  (pin_02 through pin_08 for subsequent pins)
```

### Pre-live measurement setup checklist

| Task | When |
|---|---|
| Create GA4 property for tracking domain | Before landing page publish |
| Add GA4 Measurement ID to landing page `<head>` | Before landing page publish |
| Set up outbound click event tracking for affiliate links | Before affiliate link insertion |
| Configure UTM builder sheet for all 8 pins | Before first pin publish |
| Create Pinterest business account | Before first pin publish |
| Create Pinterest board for pins | Before first pin publish |

---

## 5. Experiment Identity

Preserved from D4/D5/D6.2 without modification:

| Field | Value | Source File |
|---|---|---|
| experiment_id | `D4-HOSTINGER-PINTEREST-001` | landing_page.html:109, readme.md:7, pin_templates.md:171 |
| asset_id | `pin_set_001` | readme.md:8, pin_templates.md:188 |
| channel | `pinterest` | readme.md:10, pin_templates.md:189 |
| content_variant | `setup_guide_v1` | landing_page.html:112, readme.md:11, pin_templates.md:190 |
| destination | `/hostinger-setup-guide-v1.html` | readme.md:12 (canonical: full path on chosen host) |

**Confirmation**: No new experiment ID or asset variant is being designed. This is the same experiment, now entering the controlled publishing setup phase.

---

## 6. Human Approval Checklist

This checklist must be completed and manually verified by Omar before any go-live action.

### Affiliate / Commission Verification

- [ ] **Current Hostinger pricing verified** — Confirmed against `hostinger.com/pricing` (accessed 2026-09-01): Premium $2.99/mo (48 mo), Unlimited $3.99/mo, Cloud Startup $7.99/mo, all renew at verified rates
- [ ] **Plan names verified** — Confirmed current plan names: "Premium", "Unlimited", "Cloud Startup" (no "Single" or "Business" plans exist on current pricing page)
- [ ] **FTC disclosure present** — Disclosure text on landing page line 116: "This page contains affiliate links. If you sign up through these links, we may earn a commission at no extra cost to you."
- [ ] **Affiliate placeholders identified** — 3 placeholders in landing page at lines 119-121, 221-223, 319-321, all marked `AFFILIATE_LINK_PENDING`
- [ ] **Real affiliate links verified before insertion** — Real Impact Radius links obtained from approved Hostinger affiliate dashboard and tested (click + cookie verification)
- [ ] **Affiliate link destinations confirmed** — Each link resolves to the correct Hostinger plan page, not a generic redirect

### Content Quality

- [ ] **Landing page reviewed** — All 8 steps verified for accuracy, disclosure present, pricing correct, no misleading claims
- [ ] **Infographic reviewed** — SVG renders correctly, 8 steps accurate, pricing in Step 3 confirmed correct
- [ ] **Pins reviewed** — All 8 pin designs rendered as PNG at 1000×1500 px, text legible at mobile size, CTAs clear, no misleading claims
- [ ] **No misleading claims** — Verified: no earnings promises, no "get rich quick" language, no guaranteed results
- [ ] **No fabricated testimonials** — Verified: no testimonials present, no fake reviews, no invented user stories
- [ ] **No guaranteed earnings claims** — Verified: page states "we may earn a commission" (possibility, not guarantee), no income claims in pin text

### Technical Verification

- [ ] **Tracking configured** — GA4 property created, Measurement ID added to landing page, outbound click event tracking configured
- [ ] **Destination URL verified** — Canonical URL (`https://[username].github.io/content-money-engine/hostinger-setup-guide-v1.html`) resolves and serves the correct content
- [ ] **UTM parameters verified** — All 8 pins have correct `utm_source`, `utm_medium`, `utm_campaign`, `utm_content` parameters
- [ ] **Landing page loads on mobile** — Mobile responsiveness verified (viewport meta tag present, CSS is simple inline, no external dependencies)
- [ ] **All 8 destination anchors work** — `#step-1-purpose` through `#step-8-launch` resolve correctly (or pin URLs use full page URL with these anchors)

### Account / Platform Verification

- [ ] **Pinterest account verified** — Pinterest business account created and verified
- [ ] **Pinterest board created** — Dedicated board for Hostinger setup pins created
- [ ] **Hostinger affiliate account approved** — Impact Radius application submitted and approved (status confirmed in dashboard)
- [ ] **GitHub account verified** — GitHub account available for GitHub Pages publishing (or alternative hosting method confirmed)

### Final Sign-Off

- [ ] **All checkboxes above are checked**
- [ ] **Omar has manually reviewed all 8 pin images**
- [ ] **Omar has manually reviewed and clicked the landing page**
- [ ] **Omar has manually tested the affiliate link flow** (pin → landing page → affiliate link → Hostinger)
- [ ] **Omar approves go-live**

---

## 7. Preconditions for Going Live

These conditions must ALL be met before any publishing action:

1. **Hostinger affiliate account approved** — Application submitted via Impact Radius and status is "Approved" in the Impact dashboard.

2. **Real affiliate links obtained** — Actual tracking links from Impact Radius dashboard with verified sub-ID parameters.

3. **Affiliate links inserted** — All 3 `AFFILIATE_LINK_PENDING` placeholders replaced with real tracking links (links in `content/landing_pages/hostinger-setup-guide-v1.html` at lines 119, 221, 319 — the SVG/pin specs do not contain live links, only text markers).

4. **Landing page published** — Hosted at a public HTTPS URL (proposed: GitHub Pages).

5. **Analytics configured** — GA4 property tracking the landing page, with outbound click event tracking on affiliate links.

6. **Pin images rendered** — All 8 pins exported as PNG images at 1000 × 1500 px (from SVG and pin_templates.md specs).

7. **Pinterest business account ready** — Verified Pinterest business account with a dedicated board.

8. **UTM parameters standardized** — All 8 pin URLs use the documented UTM template with unique `utm_content` per pin.

9. **Landing page destination URL updated** — HTML metadata comment line 113 updated from `/hostinger-setup-guide` to the canonical full URL.

10. **Human approval checklist completed** — All items above checked and signed off by Omar.

### Things that do NOT need to be done for first experiment

- No custom domain required (GitHub Pages provides a URL; can be upgraded later)
- No CSS optimization (inline CSS is sufficient for a first test)
- No A/B testing setup (first experiment is single-variant)
- No email capture / newsletter required
- No SEO backlink outreach required (Pinterest is the primary channel for first experiment)

---

## 8. Risks

### Identified Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Hostinger affiliate application rejected or delayed | Medium | High | Apply early; content creation does not require approval. Have D1 #2 (Kit/ConvertKit) as fallback. |
| 2 | Pinterest algorithm changes reduce pin reach | High | Medium | Diversify to SEO backup content. Do not rely 100% on Pinterest. |
| 3 | UTM parameters break affiliate tracking | Medium | High | Test click path with cookie verification before go-live. Use GA4 event tracking on outbound clicks as independent verification. |
| 4 | Landing page URL changes after pin publishing | Low | High | Choose canonical URL before first pin publish; use permanent redirect if URL must change. |
| 5 | Pin images don't render well on mobile | Medium | Medium | Test all 8 pin PNGs at 600px display width (Pinterest mobile feed) before publishing. Ensure minimum 18px body text. |
| 6 | Destination anchors don't match landing page sections | Medium | Medium | The landing page uses `<h2>` headings without `id` attributes. The pin_templates.md references anchors like `#step-1-purpose`. These IDs must be added to the HTML before publishing. |
| 7 | Pricing changes on Hostinger site before publication | Low | Medium | Re-verify pricing immediately before go-live (D6.2 documented plan name changes already occurred once). |
| 8 | No conversions despite traffic (funnel broken) | Medium | Medium | If ≥25 landing visits but 0 Hostinger clicks → CTA placement issue. If ≥5 Hostinger clicks but 0 conversions → landing page value proposition needs work. |
| 9 | Over-publishing pins early causes audience fatigue | Low | Low | Stick to 3-day spacing for first experiment. |

### Unknown Risks

- Pinterest's current affiliate link policy (may have changed since D3 research — must verify before publishing)
- Actual Pinterest CTR for hosting tutorial pins (D3 estimated 0.5-3%; real data needed)
- Whether Impact Radius sub-ID parameters can be appended to Hostinger's standard affiliate links without breaking tracking

### Risks explicitly NOT applicable to D7

- **Phase C modification**: No source/test/config changes planned. 140/140 tests pass.
- **Workstation/OmniRoute/ResearcherAgent modification**: Not touched.
- **§26 / ResearcherAgent / ResearcherAgent**: Not touched.
- **D4 assets modification**: No changes. All D6.1 and D6.2 fixes already applied.
- **Real affiliate links**: Not inserted (placeholders only, as required).
- **Publishing**: Nothing published. All assets remain local files.

---

## 9. Exact Next Action After D7

### If D7 is approved for go-live:

1. **Apply to Hostinger affiliate program** via Impact Radius (`partners.hostinger.com`). Awaiting 5-business-day approval.

2. **Render 8 pin PNGs** from `infographic_master.svg` and `pin_templates.md` specs at 1000 × 1500 px each.

3. **Add `id` attributes** to landing page `<h2>` headings to match destination anchors in `pin_templates.md` (e.g., `<h2 id="step-1-purpose">Step 1: Choose Your Website Purpose</h2>`).

4. **Publish landing page** to GitHub Pages (or pre-existing hosting).

5. **Set up GA4** property tracking and outbound click event tracking on affiliate links.

6. **Update landing page metadata** — HTML comment on line 113 from `/hostinger-setup-guide` to the canonical full URL.

7. **Insert real affiliate links** — Replace 3 `AFFILIATE_LINK_PENDING` placeholders in `hostinger-setup-guide-v1.html` with verified Impact Radius links.

8. **Create Pinterest business account** and dedicated board.

9. **Publish Pin 1** ("Choose Your Website Purpose") with `utm_content=pin_01`.

10. **Begin 3-day cadence** — Publish Pin 2 on Day 3, Pin 3 on Day 6, etc.

11. **Monitor daily** — Check Pinterest Analytics (impressions, clicks) and GA4 (landing page visits, outbound clicks).

### If D7 is NOT approved (blocker found):

- Document the blocker
- Do not proceed to any publishing or affiliate link insertion
- Return to research phase to address the identified blocker

---

## Verification

- **Phase C**: Frozen — 140/140 tests pass (verified 2026-09-01, `python -m pytest tests/ -v`)
- **D4 assets**: All 4 files reviewed and verified present, prices aligned (D6.2), SVG syntax valid, placeholders in place
- **D5 research**: Complete, filed as research backup
- **D6 research**: Complete, all publication blockers resolved
- **D6.1 fixes**: All 3 blockers fixed (SVG tag, Single renewal price, Premium/Business pricing)
- **D6.2 alignment**: All plan names aligned to current Hostinger pricing page
- **No files modified during D7**: This document is the only deliverable. No code, config, test, or D4 asset changes.
- **No accounts created**: No Pinterest, no Impact Radius application, no GitHub Pages setup
- **No money spent**: $0
- **No affiliate links inserted**: All 3 placeholders remain as `AFFILIATE_LINK_PENDING`
- **No API keys**: None created
- **No MCP servers installed**: None
- **Workstation/OmniRoute/ResearcherAgent unchanged**: Confirmed

---

## Report

**D7 COMPLETE — READY FOR HUMAN GO-LIVE APPROVAL**

All preparation for the first controlled live experiment is documented. No publishing, affiliate accounts, API keys, or spending has occurred. The experiment is fully specified and ready for Omar's manual execution upon approval.

### Key handoff notes for Omar

1. **The single most important prerequisite**: Hostinger affiliate application must be approved before real links can be inserted. This takes up to 5 business days and is the longest single dependency.
2. **Landing page HTML has 8 `<h2>` headings without `id` attributes** — the destination anchors (`#step-1-purpose` etc.) in pin_templates.md will not work until IDs are added. This is a 8-line edit.
3. **Pricing must be re-verified** immediately before go-live — Hostinger changed plan names once already (D6.2 documented this). A quick visit to `hostinger.com/pricing` before publishing is recommended.
4. **Pin rendering is not yet done** — the SVG and pin_templates.md contain specifications, but 8 actual PNG images must be created (either by rendering the SVG and splitting, or by designing each pin individually).
5. **The experiment identity, funnel, and measurement plan are all documented** — this D7 document serves as the complete runbook for the first experiment.
