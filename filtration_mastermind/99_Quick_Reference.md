# Quick Reference Card

**Purpose:** Fast lookup for common GPT operations and responses.

---

## Response Templates

### SKU Recommendation

```markdown
**Recommended Product:**
- **SKU:** [Part number]
- **Vendor:** [Vendor name]
- **Description:** [Brief description]
- **Price:** $[Amount] (list)

**Key Specs:**
| Spec | Value |
|------|-------|
| Micron | X um [abs/nom] |
| Max Flow | X GPM |
| Max Temp | X F |
| Max Pressure | X PSI |
| Materials | [Housing/Media/Seals] |

**Why This Fits:**
[1-2 sentences on match to requirements]

**Alternatives:**
1. [SKU] - [brief reason]
2. [SKU] - [brief reason]

**Next Steps:**
[Specific action item]
```

### Requirements Summary

```markdown
## Requirements Summary

**Application:** [Type]
**Fluid:** [Description]

### Operating Conditions
| Parameter | Value | Status |
|-----------|-------|--------|
| Flow | X GPM | Confirmed / Assumed / Unknown |
| Temperature | X F | Confirmed / Assumed / Unknown |
| Pressure | X PSI | Confirmed / Assumed / Unknown |
| Micron | X um | Confirmed / Assumed / Unknown |

### Missing Information
- [ ] [Gap 1]
- [ ] [Gap 2]

### Quote Ready: Yes / No
[Explanation if No]
```

---

## Escalation Triggers (Quick Check)

| Category | Trigger | Action |
|----------|---------|--------|
| Temperature | > 400F or < 32F | Engineering |
| Pressure | > 150 PSI | Engineering |
| Chemicals | Acids, bases, solvents | Check compatibility |
| Certification | FDA, NSF, 3-A, sterile | Verify available |
| Safety | Critical system | Engineering |
| Unknown | Can't find answer | Ask or escalate |

---

## Discovery Questions (Top 10)

1. What are you filtering? (Fluid, contaminant)
2. What's the flow rate? (GPM, normal/max)
3. What's the temperature? (Operating/max)
4. What's the pressure? (Operating/max)
5. What micron rating? (Absolute or nominal?)
6. What materials work? (Housing, media, seals)
7. Certifications needed? (FDA, NSF, 3-A)
8. Current pain point? (Cost, life, performance)
9. What's being used today? (Product, vendor)
10. What's driving the change? (Problem, opportunity)

---

## Micron Quick Guide

| Micron | Size Reference | Typical Use |
|--------|----------------|-------------|
| 0.2 um | Bacteria | Sterile, pharma |
| 1 um | Large bacteria | Final filtration |
| 5 um | Red blood cell | Process water |
| 10 um | Hair diameter | General industrial |
| 25 um | White blood cell | Prefiltration |
| 50+ um | Sand grain | Straining |

---

## Temperature Limits by Family

| Family | Max Temp | Notes |
|--------|----------|-------|
| IP-DF (Depth Pleated) | 180F | PP construction |
| IP-MF (Membrane) | 180F | PES membrane |
| PF-CART (Pleated Cartridge) | 180F | Multi-media |
| CF-SHEET (Depth Sheets) | 180F | Cellulose |
| MM-SSC (Stainless) | 500F | 316SS |

---

## Top Filtration Vendors

| Vendor | SKUs | Best For |
|--------|------|----------|
| PureFilter Tech | 55 | Sanitary, F&B, housings |
| IndustrialPure | 40 | Industrial, pharma |
| ClearFlow Systems | 35 | Beverage, brewery |
| MetalMesh Pro | 20 | High temp, metal filters |
| AutoFilter Systems | 10 | Automatic, water |

---

## Swim Lane Quick Reference

| Lane | When | Focus |
|------|------|-------|
| **Pregame** | Before meeting | Research, prepare |
| **In-Meeting** | Live call | Quick answers |
| **Post-Meeting** | After call | Consolidate, gaps |
| **Pre-Quote** | Before pricing | Validate, complete |

---

## Common Conversions

| From | To | Formula |
|------|----|---------|
| GPM | LPM | x 3.785 |
| LPM | GPM | / 3.785 |
| m3/hr | GPM | x 4.4 |
| PSI | Bar | / 14.5 |
| Bar | PSI | x 14.5 |
| F | C | (F-32) x 5/9 |
| C | F | (C x 9/5) + 32 |

---

## Terminology Mapping

| User Says | System Understands |
|-----------|-------------------|
| Vendor / Supplier | Manufacturer |
| SKU / Item / Model | Part Number |
| Product Number / Catalog Number | Part Number |

**Rule:** Use the customer's preferred term in responses.

---

## File Quick Reference

| Need | File |
|------|------|
| System rules | `00_System_Instructions.md` |
| Non-negotiables | `01_Governance_Rules.md` |
| Lane behaviors | `10_Swim_Lanes.md` |
| Data structures | `30_Data_Models.md` |
| Technical concepts | `40_Filtration_Fundamentals.md` |
| Vendor info | `50_Vendor_Index.md` |
| Full SKU data | `Demo_SKU_Master.csv` |
| Chemical compat | `Demo_Chemical_Compatibility.csv` |

---

*Demo Version | Last Updated: 2026-01-13*
