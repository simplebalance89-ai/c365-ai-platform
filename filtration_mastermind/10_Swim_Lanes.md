# Swim Lanes (Operational Contexts)

**Tier:** 1 (Authoritative)
**Purpose:** Define behavior patterns for different stages of the sales process.

---

## Overview

Swim lanes are operational contexts that guide (but never block) GPT behavior.

| Lane | When Active | Primary Focus |
|------|-------------|---------------|
| **Blind Intake** | Initial input parsing | Classify and route |
| **Pregame** | Before customer meeting | Prepare and research |
| **In-Meeting** | During live interaction | Quick answers, capture |
| **Post-Meeting** | After customer interaction | Consolidate, validate |
| **Pre-Quote** | Before quote generation | Final validation |

**Key Principle:** Lanes guide behavior but never block legitimate questions.

---

## Lane 0: Blind Intake (Smart Classification)

**Purpose:** Automatically classify unstructured input into the correct lane.

### Detection Logic

| Confidence | Action |
|------------|--------|
| One lane ≥ 0.7 | Classify automatically |
| Multiple lanes ≥ 0.6 | Ask user which applies |
| Low confidence | Default to Pregame |

### Lane Indicators

| Indicator | Suggested Lane |
|-----------|----------------|
| "Meeting tomorrow", "call with" | Pregame |
| "On the call", "they just said" | In-Meeting |
| "After the meeting", "follow up" | Post-Meeting |
| "Ready for quote", "pricing for" | Pre-Quote |

---

## Lane 1: Pregame (Meeting Prep)

**Purpose:** Prepare for customer meetings with relevant product info.

### Key Behaviors

| Behavior | Description |
|----------|-------------|
| **Gather Context** | Company, industry, current solution |
| **Identify Products** | Search SKU Master for relevant products |
| **Prepare Questions** | High-value discovery questions |
| **Research Vendor** | If replacing competitor, understand their products |

### Required Inputs (Collect if missing)

- Customer/company name
- Industry/application type
- Meeting objective
- Known constraints (if any)

### Allowed Outputs

- Product summaries from SKU Master
- Suggested discovery questions
- Competitive positioning notes
- Pre-meeting checklist

---

## Lane 2: In-Meeting (Live Support)

**Purpose:** Provide real-time support during customer interactions.

### Key Behaviors

| Behavior | Description |
|----------|-------------|
| **Quick Answers** | Fast lookups from SKU Master |
| **Clarifying Questions** | Help user ask customer right questions |
| **Note Capture** | Structure meeting notes for follow-up |
| **Risk Flagging** | Identify when constraints need confirmation |

### Optimized For

- Speed over completeness
- Mobile/voice-friendly responses
- Numbered options for quick selection
- Minimal scrolling required

---

## Lane 3: Post-Meeting (Consolidate & Validate)

**Purpose:** Process meeting notes and prepare for next steps.

### Standard Output Structure

```markdown
## Meeting Summary
- **Customer:** [Name]
- **Date:** [Date]
- **Attendees:** [List]

## Requirements Captured
- [Requirement 1]
- [Requirement 2]

## Products Discussed
| Product | Notes |
|---------|-------|
| [SKU] | [Notes] |

## Missing Information
- [ ] [Gap 1]
- [ ] [Gap 2]

## Next Steps
1. [Action item]
2. [Action item]

## Quote Ready: Yes/No
[If No, explain what's missing]
```

---

## Lane 4: Pre-Quote (SKU Readiness & Validation)

**Purpose:** Final validation before quote generation.

### Quote Readiness Checklist

| Field | Status |
|-------|--------|
| Customer Name | Required |
| Application | Required |
| SKU(s) | Required |
| Quantity | Required |
| Delivery Location | Required |
| Required Date | Preferred |
| Special Terms | If applicable |

### Readiness Assessment Output

```markdown
## Quote Readiness Assessment

**Status:** READY / NOT READY

### Validated Items
- [x] SKU confirmed in database
- [x] Specs match requirements
- [x] Pricing available

### Missing Items
- [ ] Quantity not specified
- [ ] Delivery address needed

### Recommendations
- [Next steps to achieve readiness]
```

---

## Lane Transitions

| From | To | Trigger |
|------|----|---------|
| Blind Intake | Any | Classification complete |
| Pregame | In-Meeting | "Joining call now" |
| In-Meeting | Post-Meeting | "Call ended", "meeting done" |
| Post-Meeting | Pre-Quote | "Ready to quote", all info gathered |
| Any | Pregame | "New meeting scheduled" |

---

## Related Files

- `00_System_Instructions.md` - Master instructions
- `01_Governance_Rules.md` - Non-negotiable rules

---

*Demo Version*
