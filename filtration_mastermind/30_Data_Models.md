# Data Models

**Tier:** 1 (Authoritative)
**Purpose:** Define the structure of SKU, Product Family, Application, and Vendor data objects.

---

## 1. SKU Model

A **SKU** is the smallest orderable unit — the primary navigation key for all product information.

### SKU Record Schema

```yaml
sku_id: [Unique identifier - string]
manufacturer: [Manufacturer name]
description: [1-2 line product description]
product_family: [Family code if applicable]
price_usd: [List price in USD, null if unavailable]

key_specs:
  micron: [Rating + abs/nom]
  max_flow_gpm: [Gallons per minute]
  max_temp_f: [Degrees Fahrenheit]
  max_pressure_psi: [PSI]
  size: [Dimensions or connection size]
  materials: [Housing/Media/Seals]

application_type: [Primary application category]
is_filtration: [Yes/No - is this a filtration product]

constraints:
  - [List of limitations]

source_tier: [Tier 1 or Tier 2]
source_file: [Source document filename]

# Optional
alternatives: [Related SKU IDs + reason]
accessories: [Compatible accessory SKU IDs]
certifications: [FDA, NSF, 3-A, etc.]
notes: [Freeform, must be sourced]
```

### SKU Usage Rules

| Action | Rule |
|--------|------|
| **Lookup** | Search by SKU, manufacturer, application, or specs |
| **Recommend** | Max 1-3 candidates with rationale |
| **Compare** | Side-by-side on key specs |
| **Create** | NEVER — SKUs are read-only |
| **Invent Specs** | NEVER — only use documented values |

### SKU Recommendation Format

```markdown
**Recommended Product:**
- **SKU:** [ID]
- **Manufacturer:** [Name]
- **Description:** [Short description]
- **Price:** $[Amount] (list)
- **Key Specs:** [Relevant specs for this application]

**Why This Fits:**
[1-2 sentences on match to requirements]

**Considerations:**
[Any caveats, assumptions, or verification needed]
```

---

## 2. Product Family Model

A **Product Family** groups SKUs that share a common platform, media type, or application theme.

### Product Family Schema

```yaml
family_code: [Short code, e.g., "DPF"]
family_name: [Full name, e.g., "Depth Pleated Filter"]
manufacturer: [If manufacturer-specific]
category: [Cartridge, Bag, Housing, etc.]

positioning: [What it's best for]
typical_applications:
  - [Application 1]
  - [Application 2]

shared_constraints:
  - [Constraints that apply to all SKUs in family]

sku_list: [SKU IDs in this family]
```

### Family-Level Rules

- Family-level claims must be supported by Tier 1 sources
- **SKU-level data overrides family-level generalizations**
- Use families for initial filtering, then drill to SKUs

---

## 3. Application Model

An **Application** is the entry point when a SKU is unknown — describes the customer's filtration context.

### Minimum Application Profile

Collect what you can:

| Category | Fields |
|----------|--------|
| **Fluid** | Media type (water, oil, coolant, chemical) |
| **Contaminant** | Target removal (type, micron, efficiency) |
| **Flow** | Min / Normal / Max GPM |
| **Pressure** | Operating and max PSI, delta-P limits |
| **Temperature** | Normal and max range |
| **Materials** | Compatibility constraints (seals, housings, media) |
| **Environment** | Indoor/outdoor, corrosive, hazardous |
| **Maintenance** | Changeout interval, access constraints |
| **Business** | Cost target, supplier consolidation, availability |

### Common Sales Entry Patterns

| Pattern | Example | Response Strategy |
|---------|---------|-------------------|
| **Problem-first** | "Current solution too expensive" | Understand current state, identify pain |
| **Application-first** | "Need filtration for process X" | Gather operating conditions |
| **Current state** | "Using vendor Y, unknown specs" | Research vendor, ask for details |
| **Constraint-first** | "Must hit 5 micron at Y flow" | Match specs to SKUs |

### Application Reasoning Output

When no SKU is provided, produce:

```markdown
## Requirements Summary
[Brief summary of understood requirements]

## Operating Conditions
| Parameter | Value | Source |
|-----------|-------|--------|
| Flow | X GPM | [User stated / Assumed] |
| Temperature | Y°F | [User stated / Assumed] |
| Pressure | Z PSI | [User stated / Assumed] |

## Missing Information
- [ ] [Specific gap 1]
- [ ] [Specific gap 2]

## Candidate SKUs
| SKU | Vendor | Why Consider |
|-----|--------|--------------|
| [ID] | [Vendor] | [Fit reason] |

## Escalation Flags
[Any concerns requiring engineering review]
```

---

## 4. Vendor Model

A **Vendor** represents a manufacturer whose products we distribute.

### Vendor Record Schema

```yaml
vendor_name: [Canonical name]
vendor_aliases: [Alternative names/spellings]

product_types:
  - [Product category 1]
  - [Product category 2]

primary_applications:
  - [Application type 1]
  - [Application type 2]

is_filtration_vendor: [Yes/No]
sku_count: [Number of SKUs in database]

contacts: [If available]
lead_times: [Standard lead times if known]
```

### Top Vendors by SKU Count

| Vendor | SKUs | Primary Products |
|--------|------|------------------|
| SafeGuard Industries | 150 | Flame arresters, vents |
| BluePump Co | 80 | Diaphragm pumps |
| FlexFlow Pumps | 60 | Diaphragm pumps |
| PureFilter Tech | 55 | Filter housings/elements |
| IndustrialPure | 40 | Filtration elements |
| ClearFlow Systems | 35 | Depth filtration |
| ProcessTech Sensors | 25 | Process analytics |
| MetalMesh Pro | 20 | Metal/polymeric filters |
| FlowGate Valves | 20 | Butterfly/ball valves |
| PrecisionDose | 15 | Metering pumps |
| ChemSeal Products | 15 | Expansion joints, PTFE |
| ValveTech | 12 | Back pressure valves |
| DrainMaster | 10 | Condensate drains |
| AutoFilter Systems | 10 | Automatic filtration |

### Filtration Vendors

Products from these vendors are marked `Is_Filtration = Yes`:
- PureFilter Tech
- IndustrialPure
- ClearFlow Systems
- MetalMesh Pro
- AutoFilter Systems
- DrainMaster (separators)

---

## Related Files

- `Demo_SKU_Master.csv` - SKU catalog reference
- `50_Vendor_Index.md` - Detailed vendor information
- `40_Filtration_Fundamentals.md` - Technical concepts

---

*Demo Version | Last Updated: 2026-01-13*
