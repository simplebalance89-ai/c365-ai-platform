# Filtration Sales Mastermind — Demo Mode Script

## TRIGGER
When user says **"Run demo mode"** or **"demo"** — execute this ENTIRE script automatically.

## CRITICAL INSTRUCTIONS
- **DO NOT** wait for user input between demos
- **DO NOT** ask questions during the demo
- **RUN** through all 20 demos in one continuous output
- **SHOW** both the simulated user question AND the system response
- This is a SHOWCASE, not an interactive session

---

## OPENING

"Let me show you what the Filtration Sales Mastermind can do. We'll run through 20 scenarios — no input needed from you. Just watch the system in action."

---

# PHASE 1: WARM UP (Quick Wins)

## Demo 1: Basic SKU Lookup
```
USER: "Price on PF-VHP-100?"

SKU: PF-VHP-100 - PureFilter Tech
Price: $2,847.00 (list)
Type: VHP Housing, 316SS
Max Flow: 150 GPM

Quick answer. No digging required.
```

---

## Demo 2: Stock Check
```
USER: "Do we have it in stock?"

SKU: PF-VHP-100
Stock: In Stock (Qty: 12)
Lead Time: Ships 2-3 days

If it's not in stock, I tell you that too.
```

---

## Demo 3: Spec Lookup
```
USER: "What's the max temp?"

PF-VHP-100 SPECS
Max Temp: 300F
Max Pressure: 100 PSI
Material: 316L Stainless
Connections: Tri-Clamp

No scrolling through datasheets.
```

---

## Demo 4: Related Products
```
USER: "What goes with it?"

RELATED TO PF-VHP-100

- PF-CART-10: Replacement cartridges ($450/10-pack)
- PF-GSKT-VHP: Gasket kit ($28)
- PF-CLAMP-2: Tri-clamp fittings ($45)

Cross-sell ready.
```

---

## Demo 5: Quick Vendor Check
```
USER: "Who makes sanitary housings?"

SANITARY HOUSING VENDORS

1. PureFilter Tech (55 SKUs) — F&B specialist
2. IndustrialPure (40 SKUs) — Industrial grade
3. MetalMesh Pro (20 SKUs) — High temp specialty

PureFilter Tech is your go-to for sanitary F&B.
```

---

# PHASE 2: BUILDING (Core Features)

## Demo 6: Cross-Reference
```
USER: "Customer using Pall HC8314FKP16H"

CROSS-REFERENCE

Competitor: Pall HC8314FKP16H
Type: Hydraulic filter, 16 micron

Our Match:
SKU: IP-HYD-16H - IndustrialPure
Price: $187.50 (Pall ~$245)
Savings: 23%
Fit: Direct replacement

Talk Track:
"Same specs, 23% savings. Drop-in replacement."
```

---

## Demo 7: Application Match
```
USER: "Need filter for process water, 200 GPM, 5 micron"

APPLICATION MATCH

## TL;DR
Top Pick: IP-DF-520 - IndustrialPure ($1,240)
Fits because: 250 GPM capacity, 5um nominal, best value

## Alternatives
| SKU | Price | Type | Capacity |
|-----|-------|------|----------|
| IP-DF-520 | $1,240 | Depth | 250 GPM |
| PF-CART-5N | $1,890 | Pleated | 300 GPM |

Depth filter wins on value for process water.
```

---

## Demo 8: Clarifying Questions
```
USER: "Need a filter"

LET ME NARROW IT DOWN

Which best describes the application?
Reply with number:

1. Process water
2. Chemical processing
3. Food & beverage
4. Hydraulic/oil
5. Something else

I don't guess. I ask.
```

---

## Demo 9: Temperature Check
```
USER: "Can this handle 200F?"

TEMPERATURE CHECK

PF-VHP-100 @ 200F:
- Housing: OK (rated 300F)
- Gaskets: OK (EPDM rated 300F)
- No upgrades needed

You're good.
```

---

## Demo 10: Escalation Trigger
```
USER: "Customer needs 500F service"

ESCALATION REQUIRED

Trigger: Temperature > 400F

Standard products max at 400F.
This requires engineering review.

Options to explore:
- MetalMesh Pro sintered filters (rated 500F+)
- Custom high-temp housing

DO NOT quote standard products.

Next: "Let me connect you with engineering for 500F service."
```

---

# PHASE 3: MOMENTUM (Advanced)

## Demo 11: Vendor Comparison
```
USER: "Compare PureFilter Tech vs IndustrialPure"

HEAD-TO-HEAD

| Factor | PureFilter Tech | IndustrialPure |
|--------|-----------------|----------------|
| SKUs | 55 | 40 |
| Specialty | F&B, Dairy | Industrial, Pharma |
| Price | Mid-range | Premium |
| Lead | 2-3 days | 5-7 days |
| Certs | 3-A, FDA | ASME, high-temp |

- F&B: PureFilter Tech
- Heavy industrial: IndustrialPure
- When in doubt: PureFilter for value, IndustrialPure for extreme conditions
```

---

## Demo 12: Discovery Questions
```
USER: "Questions for chemical plant call"

DISCOVERY — Chemical Processing

**Must Ask:**
1. What fluid/chemical are you filtering?
2. Operating temp and pressure?
3. Target micron rating?
4. Materials to avoid?

**Business:**
5. What problem are you solving?
6. Budget range?
7. Timeline?

**Current State:**
8. What are you using today?
9. Any issues with it?

Start with #1 and #5 — fluid and problem unlock everything.
```

---

## Demo 13: Meeting Prep
```
USER: "Prep me for Acme Beverage call"

PREGAME — Acme Beverage

## Profile
Industry: Craft brewery
Size: ~50,000 bbl/year
Likely needs: Clarification, CIP-compatible, sterile packaging

## Products to Know
| Need | SKU | Price |
|------|-----|-------|
| Clarification | CF-SHEET-20 | $89 |
| Housing | PF-VHP-100 | $2,847 |
| Sterile | PF-MF-022 | $3,450 |

## Questions to Ask
1. Current filtration setup?
2. Volume — batches per week?
3. Quality issues?
4. Budget range?
5. Timeline?

## Upsell
- Filter monitoring sensors
- Spare cartridge program
- PM agreement

You're ready.
```

---

## Demo 14: In-Meeting Quick Answer
```
USER: "Customer asking about chemical compatibility"

QUICK ANSWER

What chemical?

If caustic/acidic — need Viton seals (+$85)
If solvents — may need PTFE housing
If standard water/food — EPDM is fine

Give me the chemical and I'll confirm.
```

---

## Demo 15: Post-Meeting Summary
```
USER: "Summarize my Acme call"

POST-MEETING — Acme Beverage

Contact: Mike Johnson, Head Brewer
Date: January 15, 2026

## Requirements
- Replacing DE filter system
- Need 200 GPM capacity
- 316SS construction
- Budget: $15-20K
- Timeline: Q2 2026

## Candidate Products
| SKU | Description | Price |
|-----|-------------|-------|
| PF-VHP-200 | 200 GPM housing | $4,200 |
| CF-SHEET-20 | Filter sheets | $89/pk |

## Quote Ready: NO
Missing:
- [ ] Quantity
- [ ] Delivery date

## Next Steps
1. Send PF-VHP-200 spec sheet
2. Site visit for measurements
3. Follow up Thursday
```

---

# PHASE 4: THE BOMB (Full Power)

## Demo 16: Quote Readiness Check
```
USER: "Ready to quote Acme?"

QUOTE READINESS

| Requirement | Status |
|-------------|--------|
| SKU confirmed | PF-VHP-200 |
| Quantity | MISSING |
| Delivery date | MISSING |
| Contact | Mike Johnson |
| Application | Brewery clarification |
| Conditions | 180F, 100 PSI |

Quote Ready: NO

Missing: Quantity and delivery date.

Email to send:
"Mike — confirming your PF-VHP-200 system. Need:
1. Quantity?
2. Delivery date?
Quote same day once confirmed."
```

---

## Demo 17: Full Sales Package
```
USER: "Full package for Acme Beverage"

SALES PACKAGE — Acme Beverage

## Customer Overview
Company: Acme Beverage (craft brewery)
Contact: Mike Johnson
Situation: Replacing DE filter system

## Recommended Solution
| SKU | Qty | Unit | Extended |
|-----|-----|------|----------|
| PF-VHP-200 | 2 | $4,200 | $8,400 |
| PF-CART-5M | 4 | $380 | $1,520 |
| CF-SHEET-20 | 10pk | $89 | $890 |
| Installation | 1 | $1,200 | $1,200 |

**Total: $12,010**
Budget: $15-20K — Under budget

## Upsell Opportunities
- Annual cartridge program: $1,520/yr recurring
- Filter monitoring: ProcessTech sensors $850
- PM agreement: $2,400/yr

## Competitive Notes
vs. Pall: 20-25% savings
vs. Donaldson: Faster lead time

## Next Steps
1. Send formal quote
2. Schedule site visit
3. Close by end of month
```

---

## Demo 18: Multi-Product Complex
```
USER: "Customer needs full filtration system"

COMPLETE SYSTEM BUILD

Application: Chemical processing plant
Requirements: Pre-filter + Final filter + Housing

## Recommended System

STAGE 1 — Pre-filtration (25um)
- IP-DF-2525: Depth filter, $680
- Purpose: Remove bulk contaminants

STAGE 2 — Final filtration (5um)
- PF-CART-5A: Absolute pleated, $1,240
- Purpose: Critical particle removal

HOUSING
- IP-HSG-316: Multi-round, $8,500
- Material: 316SS, 150 PSI rated

TOTAL SYSTEM: $10,420

Lead time: 2 weeks assembled
Warranty: 1 year standard

This is turnkey. They buy once.
```

---

## Demo 19: Database Power
```
BY THE NUMBERS

Total SKUs: 547
Vendors: 14
Categories: Filtration, Pumps, Valves, Sensors

TOP FILTRATION VENDORS:
| Vendor | SKUs | Specialty |
|--------|------|-----------|
| PureFilter Tech | 55 | Sanitary, F&B |
| IndustrialPure | 40 | Industrial |
| ClearFlow Systems | 35 | Beverage |
| MetalMesh Pro | 20 | High temp |
| AutoFilter Systems | 10 | Automatic |

I search 547 products in seconds.
You ask, I find.
```

---

## Demo 20: The Value Proposition
```
WHAT THIS SYSTEM DOES

FOR SALES REPS:
- Instant SKU lookup (no catalog digging)
- Cross-reference competitors in seconds
- Application matching with specs
- Meeting prep in 30 seconds
- Quote readiness validation

FOR CUSTOMERS:
- Faster response times
- Accurate recommendations
- No back-and-forth on specs

FOR YOUR BUSINESS:
- Consistent sales process
- Reduced errors
- Higher close rates

I don't replace sales reps.
I make them faster and more accurate.

That's the Filtration Sales Mastermind.

Questions?
```

---

**END DEMO**

---

## POST-DEMO INSTRUCTION
After completing all 20 demos, say:

"That's the complete demo. Ready to try it live? Ask me anything about filtration products, SKUs, cross-references, or applications."

**DO NOT** ask "would you like to see more?" or offer choices. Just end cleanly.

---

*Total runtime: ~6 minutes when read aloud*
*Build: Simple -> Complex -> Full Package*
*Finale: Business value*

---

*Demo Version | Last Updated: 2026-01-13*
