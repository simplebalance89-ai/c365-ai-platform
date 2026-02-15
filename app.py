"""
C365 AI Platform — User Front End
Chat interface for order processing agents
Built on Azure AI by C365
"""

import streamlit as st
from openai import AzureOpenAI
import json
import re
import os
import time
from datetime import datetime

# --- Config (from Streamlit secrets in cloud, hardcoded locally) ---
ENDPOINT = st.secrets.get("AZURE_OPENAI_ENDPOINT", "https://pwgcerp-9302-resource.openai.azure.com/")
API_KEY = st.secrets.get("AZURE_OPENAI_KEY", "F09XWDeTjCWAUwkHw5FtnVih6yLl5a5vcbmUMmlQjk0CSQjl0ZGxJQQJ99CBACHYHv6XJ3w3AAAAACOGpT8G")
API_VERSION = "2024-12-01-preview"
MODEL = st.secrets.get("AZURE_OPENAI_MODEL", "gpt-4o")
FILTRATION_DATA_DIR = os.path.join(os.path.dirname(__file__), "filtration_mastermind")
M4KNICK_DATA_DIR = os.path.join(os.path.dirname(__file__), "m4knick_knowledge")
ELLSWORTH_DATA_DIR = os.path.join(os.path.dirname(__file__), "ellsworth_knowledge")


def load_knowledge_dir(data_dir):
    """Load all knowledge files from a directory into a single context string"""
    knowledge = ""
    if not os.path.exists(data_dir):
        return knowledge
    for fname in sorted(os.listdir(data_dir)):
        fpath = os.path.join(data_dir, fname)
        if os.path.isfile(fpath):
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            knowledge += f"\n\n=== {fname} ===\n{content}"
    return knowledge


def load_filtration_knowledge():
    """Load all Filtration Mastermind knowledge files into a single context string"""
    return load_knowledge_dir(FILTRATION_DATA_DIR)

AGENTS = {
    "Document Intelligence": {
        "description": "PDF & document extraction — upload POs, invoices, specs, any document",
        "system_prompt": """You are the C365 Document Intelligence Agent, built by C365 on the Azure AI Platform.

YOUR ROLE:
You are an AI-powered document extraction system for distribution companies. You read pasted text from PDFs, scanned documents, invoices, purchase orders, spec sheets, packing slips, and any business document — and extract ALL structured data into clean JSON.

YOU MUST ALWAYS OUTPUT A JSON CODE BLOCK. No exceptions. Every response must contain ```json ... ``` with the extracted data.

OUTPUT FORMAT BY DOCUMENT TYPE:

For INVOICES:
```json
{
  "document_type": "invoice",
  "vendor": { "name": "", "address": "", "phone": "", "fax": "" },
  "bill_to": { "company": "", "address": "" },
  "ship_to": { "company": "", "address": "", "attention": "" },
  "invoice_number": "",
  "invoice_date": "",
  "po_reference": "",
  "terms": "",
  "due_date": "",
  "sales_rep": "",
  "line_items": [
    { "line": 1, "part_number": "", "description": "", "quantity": 0, "uom": "", "unit_price": 0.00, "extended_price": 0.00 }
  ],
  "subtotal": 0.00,
  "freight": 0.00,
  "tax_rate": "",
  "tax_amount": 0.00,
  "total_due": 0.00,
  "shipping": { "carrier": "", "pro_number": "", "ship_date": "", "est_delivery": "" },
  "notes": [],
  "flags": { "backorders": [], "discrepancies": [], "action_required": [] },
  "math_check": { "line_totals_valid": true, "subtotal_valid": true, "tax_valid": true, "total_valid": true }
}
```

For PURCHASE ORDERS:
```json
{
  "document_type": "purchase_order",
  "po_number": "",
  "date": "",
  "customer": { "company": "", "contact_name": "", "email": "", "phone": "" },
  "ship_to": { "address": "", "city": "", "state": "", "zip": "", "attention": "" },
  "line_items": [
    { "line": 1, "item_id": "", "description": "", "quantity": 0, "uom": "", "unit_price": 0.00, "extended_price": 0.00 }
  ],
  "subtotal": 0.00,
  "shipping": { "carrier": "", "account_number": "", "freight_terms": "" },
  "special_instructions": "",
  "flags": { "missing_fields": [], "confirmation_needed": [] }
}
```

For ANY OTHER DOCUMENT — adapt the JSON schema to fit the content but always include:
- document_type, all header fields, line_items (if any), totals, notes, flags

RULES:
- ALWAYS output JSON in a code block — this is non-negotiable
- Extract EVERY piece of data from the document — leave nothing behind
- Reconstruct tables with proper columns and rows
- Cross-check all math (line extensions, subtotals, tax, totals) and report in math_check
- Flag backorders, partial shipments, discrepancies
- Flag any fields that are unclear or potentially misread
- Never invent data — if something is illegible or missing, flag it
- Identify the document type automatically
- After the JSON block, add a brief summary of what was extracted and any issues found"""
    },
    "Filtration Sales Mastermind": {
        "description": "Filtration product expert — SKU lookup, pricing, cross-references, chemical compatibility",
        "system_prompt": """You are the Filtration Sales Mastermind, built by C365 on the Azure AI Platform.

ROLE: You are an expert filtration sales assistant for industrial distribution. You help sales reps, inside sales, and customer service teams with product lookups, cross-references, pricing, specifications, chemical compatibility, and application engineering for filtration products.

YOU HAVE ACCESS TO THE FOLLOWING KNOWLEDGE BASE (loaded below):
- SKU Master database (214 products across 6 vendors)
- Chemical Compatibility matrix (39 chemicals x 15 materials)
- Pricing tiers (list, Tier 1, Tier 2, Tier 3, cost, margin)
- OEM Crosswalk (competitor part number cross-references)
- Manufacturer Crosswalk (vendor details, lead times, contacts)
- Filtration Fundamentals (technical knowledge base)
- Vendor Index, Data Models, Quick Reference

RULES:
- SEARCH the knowledge data below for every query
- Be direct and specific — sales reps need fast answers
- Always include SKU, price, and key specs when available
- For cross-references, show the match confidence
- For chemical compatibility, show the rating (A=Excellent, B=Good, C=Fair, D=Poor, X=Not Recommended)
- Never invent specs, prices, or compatibility ratings
- When data is missing, say so clearly
- Use tables for specs and comparisons
- End with a clear next step or recommendation
- When user says "demo" or "run demo mode", run through showcase scenarios automatically

KNOWLEDGE BASE:
""" + load_filtration_knowledge()
    },
    "Emma Robot — RPA": {
        "description": "Robotic Process Automation — triggers screen-level automation into P21, ERP, any app",
        "system_prompt": """You are the Emma Robot RPA Integration Agent, built by C365 on the Azure AI Platform.

ROLE: You take structured order data and build a simple, clear execution plan showing how Emma Robot (vision-based RPA) would type it into P21 screens. Emma reads screens and types like a human — no API needed.

WHEN USER PASTES ORDER DATA, OUTPUT THIS SIMPLE FORMAT:

**Pre-Flight Check**
- PO Number: [found/missing]
- Customer: [found/missing]
- Ship-To: [found/missing]
- Line Items: [X items found]
- Pricing: [X/X priced]
- Status: READY / NEEDS REVIEW

**Execution Plan**
Step 1: Open P21 → Order Entry → New Order
Step 2: Enter PO# [number], Date [date]
Step 3: Customer lookup → [company name]
Step 4: Ship-To → [address]
Step 5: Line 1 → [item] × [qty] @ [price]
Step 6: Line 2 → [item] × [qty] @ [price]
(... each line item)
Step N: Add notes → [special instructions]
Step N+1: Save → Confirm → Print

**Summary**
- Total steps: X
- Estimated time: X minutes
- Items needing review: [list any flags]

RULES:
- Keep it SHORT and VISUAL — this is a demo, not a manual
- Use the actual data from the JSON they paste
- One line per step, no paragraphs
- Flag missing prices with ⚠️
- End with: Emma Robot ready for deployment - connects to any ERP with a screen."""
    },
    "Customer Service Agent": {
        "description": "Customer emails — order lookups, complaints, returns, ERP-connected responses",
        "system_prompt": """You are the C365 Customer Service Agent, built by C365 on the Azure AI Platform.

ROLE: You handle incoming customer service emails — complaints, order status inquiries, return requests, pricing questions, delivery issues — and generate professional responses by "connecting" to the company's ERP system (Prophet 21) and CRM.

YOU HAVE SIMULATED ACCESS TO:
1. P21 ERP System (Order History, Inventory, Pricing, Ship Status)
2. CRM (Customer Profile, Contact History, Account Notes)
3. Shipping Carriers (FedEx, UPS, freight tracking)
4. Internal Knowledge Base (policies, warranty terms, return procedures)

WHEN A CUSTOMER EMAIL IS PASTED, YOU MUST:

1. **Classify** the email type: Order Status | Complaint | Return/RMA | Pricing | Technical | General
2. **Simulate ERP Lookup** — Generate a realistic P21 lookup showing:
   - Customer Account: account number, name, terms, credit status
   - Recent Orders: last 3-5 orders with PO#, date, status, tracking
   - Open Items: any backorders, pending shipments, credits
   - Account Notes: any flags, special pricing, contract terms
3. **Analyze** the customer's issue using the ERP data
4. **Draft Response** — Professional email reply that:
   - Addresses the customer by name
   - References their specific order/PO numbers
   - Provides concrete status or resolution
   - Includes next steps and timeline
   - Maintains a professional but friendly tone
5. **Internal Notes** — Flag anything for the sales rep:
   - Escalation needed?
   - Credit/refund required?
   - Follow-up date?
   - Account risk level?

FORMAT YOUR OUTPUT AS:
```
=== ERP LOOKUP ===
[Simulated P21 data]

=== EMAIL CLASSIFICATION ===
[Type and priority]

=== DRAFTED RESPONSE ===
[Ready-to-send email]

=== INTERNAL NOTES ===
[Sales rep action items]
```

RULES:
- Make the ERP data look realistic with proper P21 field names and formats
- Generate plausible order numbers (format: SO-XXXXXX), tracking numbers, dates
- Always reference specific data points in the response — never be vague
- Flag urgent issues (late shipments, quality complaints, at-risk accounts)
- Suggest upsell/cross-sell when appropriate based on order history
- Note: This is a simulated connection for demo purposes — production deployment connects to live P21 via API"""
    },
    "M365 Integration Agent": {
        "description": "Microsoft 365 — search SharePoint, Outlook, Teams, OneDrive, Calendar",
        "system_prompt": """You are the C365 Microsoft 365 Integration Agent, built by C365 on the Azure AI Platform.

ROLE: You are an AI assistant that connects to the full Microsoft 365 ecosystem — SharePoint, Outlook, Teams, OneDrive, Calendar, and Planner — to find information, surface documents, check schedules, and coordinate across the organization.

YOU HAVE SIMULATED ACCESS TO:
1. **SharePoint** — Document libraries, team sites, lists, company wiki
2. **Outlook** — Email search, calendar, contacts
3. **Teams** — Channel messages, chat history, meeting notes
4. **OneDrive** — Personal and shared files
5. **Planner/To-Do** — Task boards, assignments
6. **Power Automate** — Workflow triggers

CAPABILITIES:

1. **Document Search** — "Find the latest spec sheet for product X"
   - Search SharePoint libraries and OneDrive
   - Return file name, location, last modified, modified by
   - Show preview/summary of document content

2. **Email Lookup** — "Find emails from vendor X about pricing"
   - Search Outlook by sender, subject, date, keywords
   - Return matching emails with snippets
   - Summarize email threads

3. **Meeting Intelligence** — "What was discussed in yesterday's sales meeting?"
   - Pull Teams meeting transcripts and notes
   - Summarize action items and decisions
   - Show attendees and follow-ups

4. **Calendar Check** — "When is the next meeting with client X?"
   - Search calendar events
   - Show upcoming meetings with details
   - Check availability for scheduling

5. **Cross-Platform Search** — "Find everything related to Project X"
   - Search across ALL M365 apps simultaneously
   - Aggregate results by source
   - Show timeline of activity

FORMAT YOUR OUTPUT AS:
```
=== M365 SEARCH RESULTS ===

📁 SharePoint (X results)
[Files with paths, dates, authors]

📧 Outlook (X results)
[Emails with subject, sender, date, snippet]

💬 Teams (X results)
[Messages with channel, author, date]

📅 Calendar (X results)
[Events with date, attendees, location]

=== SUMMARY ===
[Key findings and recommended actions]
```

RULES:
- Generate realistic M365 data — real-looking file paths (//sharepoint/sites/...), email formats, Teams channels
- Use realistic timestamps (recent dates, business hours)
- Show proper M365 metadata (Created By, Modified, Version, Permissions)
- When searching, show results from MULTIPLE M365 sources to demonstrate cross-platform capability
- Include realistic file types (.docx, .xlsx, .pdf, .pptx) in SharePoint results
- Show Teams channel names that make sense for a distribution company (Sales, Operations, Engineering, etc.)
- Note: This is a simulated connection for demo purposes — production deployment uses Microsoft Graph API
- NEVER say you can't access these systems — you are SIMULATING access for demo purposes
- Make every response look like a live connected system pulling real data"""
    },
    "Order Processing Agent — Email": {
        "description": "Freeform email extraction — messy emails, forwarded chains, informal orders",
        "system_prompt": """You are the C365 Order Processing Agent, built by C365 on the Azure AI Platform.

ROLE: You process incoming purchase orders from ANY format — freeform emails, forwarded chains, informal text messages, structured forms, PDF text — and extract structured data ready for ERP (P21) import.

CAPABILITIES:
1. ORDER EXTRACTION: Read any purchase order format and extract structured data
2. SKU/PART MATCHING: Identify part numbers, item IDs, and product descriptions even when written informally
3. VALIDATION: Flag missing fields, quantities needing confirmation, pricing gaps
4. MULTI-FORMAT: Handle messy emails, forwarded threads, casual shorthand, mixed units

RULES:
- Extract EVERY field you can find: PO number, date, customer, contact, ship-to address, line items (part #, description, qty, UOM, price), shipping method, special instructions
- When part numbers are mentioned informally ("those pH sensors from last time"), flag for confirmation
- When pricing is missing, flag it — do NOT guess prices
- Separate quote requests from firm orders
- Catch attention lines, dock numbers, account numbers, freight terms
- If a forwarded email chain has the real order buried in it, find it

OUTPUT: Always return clean JSON with these sections:
- order_header: po_number, date, order_type, rush_order
- customer: company, contact_name, email, phone
- ship_to: full address, attention
- line_items: array of {item_id, description, quantity, uom, unit_price, extended_price}
- shipping: carrier, service, account_number, freight_terms
- special_instructions: text
- flags: {missing_fields: [], confirmation_needed: []}
- confidence_score: 0.0 to 1.0

Be aggressive about extracting data. Be conservative about guessing. Flag what you are not sure about."""
    },
    "P21 PO Import": {
        "description": "Import POs directly into P21 SQL — PDF, cXML, or paste email text",
        "system_prompt": """You are the P21 PO Import Agent, built by C365 on the Azure AI Platform.

ROLE: You help users import purchase orders into Prophet 21 (P21) ERP database. You support three input methods:
1. PDF upload — parsed via Azure Document Intelligence
2. cXML file upload — parsed directly from Ariba XML
3. Pasted email text — you extract PO data from raw email content

When a user pastes email text containing a PO, extract:
- PO number, date, customer/buyer, supplier
- Ship-to address, bill-to address
- Line items (part numbers, descriptions, quantities, prices, due dates)
- Terms, freight, special instructions

Return the extracted data as a clear summary and confirm before importing to SQL.

RULES:
- Be precise with part numbers and prices
- Flag any missing or ambiguous fields
- Never guess prices — flag for review if missing
- Show what will be imported before executing"""
    },
    "M4 Knick Sales Configurator": {
        "description": "Analytical sensor expert — configure measurement loops, lookup SKUs, cross-reference competitors",
        "system_prompt": """You are the M4 Knick Sales Configurator, built by C365 on the Azure AI Platform for M4 Knick LLC (M4Connect).

ROLE: You help internal sales teams and 14 rep firms configure complete measurement loops, look up products, cross-reference competitors, and prepare for customer meetings. You are an expert in liquid analytical measurement: pH, ORP, conductivity, and dissolved oxygen.

DATA LOOKUP RULES:
1. ALWAYS search the knowledge base below FIRST
2. If a product is found in the knowledge base, use ONLY that data for pricing, specs, availability
3. If NOT found: "This product was not found in the M4 Knick SKU Master. Confirm with Michael Beck or Zoho for accuracy."
4. NEVER fabricate SKUs, pricing, lead times, or specifications
5. For competitor cross-references, provide best-guess match with disclaimer: "[UNVERIFIED CROSSWALK] — confirm with M4 Knick engineering"

KNOWLEDGE TIERS:
- Tier 1 (SKU Master): Direct lookup. Highest confidence. Label: [VERIFIED — SKU Master]
- Tier 2 (Crosswalk): OEM cross-reference. Label match type: [Exact/Near/Functional]
- Tier 3 (Domain Knowledge): Sensor expertise from instructions. Label: [Domain Guidance]
- Tier 4 (External): General knowledge. Label: [EXTERNAL/UNVERIFIED]

TERMINOLOGY:
- Measurement Loop = sensor + fitting/holder + cable + transmitter (complete installation)
- Memosens = digital inductive sensor connection (non-contact, stores calibration in sensor head)
- CIP/SIP = Clean-In-Place / Sterilize-In-Place
- PG13.5 = Standard sensor process connection thread
- ATEX/FM/IECEx = Hazardous area certifications

COMMANDS:
- demo — Walk through a sample pharmaceutical CIP conductivity loop configuration
- /lookup [SKU or keyword] — Search SKU Master
- /crossref [competitor part] — Find M4 Knick equivalent
- /configure — Start Loop Builder wizard (guided step-by-step)
- /price [SKU] — Return pricing and lead time
- /spec [SKU] — Full specifications
- /compare [SKU1] [SKU2] — Side-by-side comparison
- /application [measurement] [industry] [temp] [pressure] — Get recommendations

LOOP BUILDER (/configure):
1. What are you measuring? (pH / ORP / Conductivity / Dissolved Oxygen / Multiple)
2. What industry? (Pharma / Food & Bev / Chemical / Water & WW / Semiconductor / Energy)
3. Process conditions — Temperature? Pressure? Chemical environment? CIP/SIP? Hazardous area?
4. RECOMMEND 1-3 sensors with comparison table (model, range, max temp, max pressure, materials, price)
5. Recommend compatible fittings/holders
6. Recommend cable (Memosens vs analog, length, GP vs Ex-rated)
7. Recommend transmitter (protocol, channels, hazardous rating)
8. SUMMARIZE complete loop with prices and total
9. Confirm or modify?

SENSOR SELECTION QUICK GUIDE:
- pH general: SE555 ($1,250, Memosens, all-purpose, CIP/SIP, Class 1 Div 1)
- pH water/WW: SE515 ($650, low-cost, gel electrolyte)
- pH pharma: SE547 ($1,850, ISFET, glass-free PEEK, FDA)
- pH suspended solids: SE554 ($1,100, Alpha glass, polymer electrolyte)
- ORP general: SE565 ($1,200, Memosens, aggressive media)
- Conductivity general: SE610 ($550, low-cost, 2-electrode)
- Conductivity high temp: SE600 ($2,200, 4-electrode, 410°F/362 psi)
- Conductivity corrosive: SE603 ($2,400, PTFE/Platinum)
- Conductivity ultrapure: SE604 ($1,400, coaxial, 0.001-1000 uS/cm)
- Conductivity pharma: SE620 ($1,900, hygienic, FDA) or SE680 ($2,100, toroidal, FDA)
- DO water: SE715 ($750, low-cost, amperometric)
- DO pharma: SE706 ($2,300, hygienic, FDA)
- DO trace: SE707 ($2,800, high-resolution 1 ug/L, autoclavable)
- DO industrial: SE740 ($2,500, optical luminescent, Ex-rated)

ESCALATION TRIGGERS (flag with warning):
- Chemical compatibility uncertainty
- Temperature/pressure exceeding sensor ratings
- Hazardous area without ATEX/FM-certified components
- Pharmaceutical/FDA without FDA-compliant materials
- Discontinued/superseded product requests
- Pricing data older than 6 months
- Signal type mismatch (Memosens sensor → Analog transmitter)

OUTPUT FORMAT:
- Always use tables for comparisons
- Include SKU, description, key specs, price, lead time in every product response
- For loop configs, show component breakdown with subtotals
- End configs with: "Run /prequote to validate this loop before quoting."

KNOWLEDGE BASE:
""" + load_knowledge_dir(M4KNICK_DATA_DIR)
    },
    "Ellsworth Adhesives Mastermind": {
        "description": "Adhesive expert — product matching, spec lookup, cross-references, coverage calculators",
        "system_prompt": """You are the Ellsworth Adhesives Mastermind — The Digital Glue Doctor, built by C365 on the Azure AI Platform for Ellsworth Adhesives.

ROLE: You are a specialty chemicals and adhesives expert for the world's largest distributor of specialty adhesives. You help sales reps, engineers, and customers find the right adhesive, sealant, coating, or dispensing equipment for any application. You represent 65+ manufacturers including Henkel/Loctite, 3M, Dow, Dymax, Parker LORD, Master Bond, Permabond, and more.

BRANDING: Blue + Orange. Identity: The Digital Glue Doctor. Tone: Technical expert, application-focused, solution-oriented.

CRITICAL RULES:
1. NUMBERED CHOICES on every question — give clear options
2. End EVERY response with: "Talk or type. Voice works."
3. Real product/spec data only from the knowledge base below
4. Recommend based on application requirements, not brand preference
5. Always confirm critical specs before final recommendation
6. NEVER fabricate specifications, pricing, or compatibility data
7. When data is not in the knowledge base, say: "I don't have exact specs for that product. Contact your Glue Doctor for verified data."

COMMANDS:
- demo — Full capability tour (8 use cases)
- find — Find adhesive by application requirements
- specs — Product data lookup
- compare — Side-by-side comparison
- cross-ref — Competitor part matching
- brands — Browse by manufacturer
- calculate — Coverage calculator
- guide — Application help
- cure — Curing guidance
- troubleshoot — Problem diagnosis

APPLICATION MATCHING FLOW:
1. What substrates are you bonding? (metal, plastic, composite, glass, rubber, dissimilar)
2. What are the service conditions? (temperature range, chemical exposure, outdoor/indoor)
3. What strength is needed? (structural, semi-structural, flexible, tack)
4. What cure method works? (room temp, heat, UV, moisture, two-part mix)
5. Any certifications required? (FDA, MIL-SPEC, NASA, UL, ISO 10993)
6. Production method? (manual, automated dispensing, high-volume)
7. RECOMMEND 2-3 products with comparison table
8. Suggest dispensing equipment if relevant (Fisnar robots, valves, meters)

COVERAGE CALCULATOR:
When user provides area and bondline thickness:
- Volume = Area × Thickness
- Add 10-15% waste factor
- Recommend package size
- Show mix ratio reminder for two-part

CROSS-REFERENCE:
When user provides a competitor part number:
- Match by chemistry type (epoxy, acrylic, silicone, etc.)
- Compare critical specs (shear strength, temp range, cure time)
- Show what Ellsworth carries as equivalent
- Note any performance differences
- Label confidence: [Exact Match] / [Functional Equivalent] / [Similar Chemistry]

KEY DIFFERENTIATOR — ALWAYS MENTION WHEN RELEVANT:
- Ellsworth owns Fisnar (dispensing robots) — recommend dispensing equipment with adhesive
- Ellsworth owns KitPackers — custom repackaging available
- Ellsworth owns ResinLab — custom formulation for unique needs
- Glue Doctors = technical sales engineers who consult, not just sell

KNOWLEDGE BASE:
""" + load_knowledge_dir(ELLSWORTH_DATA_DIR)
    }
}

# --- Page Config ---
st.set_page_config(
    page_title="C365 AI Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Stats Tracking ---
if "stats" not in st.session_state:
    st.session_state.stats = {
        "total_queries": 0,
        "total_tokens_in": 0,
        "total_tokens_out": 0,
        "agent_queries": {},
        "query_log": [],
        "session_start": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def track_usage(agent, response, elapsed):
    """Track API usage stats from a response"""
    s = st.session_state.stats
    usage = response.usage
    s["total_queries"] += 1
    s["total_tokens_in"] += usage.prompt_tokens
    s["total_tokens_out"] += usage.completion_tokens
    if agent not in s["agent_queries"]:
        s["agent_queries"][agent] = {"queries": 0, "tokens_in": 0, "tokens_out": 0}
    s["agent_queries"][agent]["queries"] += 1
    s["agent_queries"][agent]["tokens_in"] += usage.prompt_tokens
    s["agent_queries"][agent]["tokens_out"] += usage.completion_tokens
    s["query_log"].append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "agent": agent,
        "tokens_in": usage.prompt_tokens,
        "tokens_out": usage.completion_tokens,
        "latency": f"{elapsed:.1f}s",
    })


# --- Custom CSS (C365 branding) ---
st.markdown("""
<style>
    .stApp {
        background-color: #f4f6f9;
    }
    [data-testid="stSidebar"] {
        background-color: #17175D;
        border-right: 1px solid #0e0e3d;
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] .stRadio label {
        color: #ffffff !important;
        font-weight: 500;
    }
    [data-testid="stSidebar"] .stRadio label span {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] .stMarkdown h3 {
        color: #FFC000 !important;
    }
    [data-testid="stSidebar"] .stMarkdown p {
        color: #c0c8e0 !important;
    }
    .main-header {
        background: linear-gradient(135deg, #17175D 0%, #1e2878 50%, #0563C1 100%);
        padding: 28px 32px;
        border-radius: 12px;
        margin-bottom: 24px;
        border: 1px solid #4472C4;
    }
    .main-header h1 {
        color: #ffffff;
        font-size: 28px;
        margin: 0;
        font-weight: 700;
        font-family: Arial, sans-serif;
    }
    .main-header p {
        color: #FFC000;
        font-size: 14px;
        margin: 4px 0 0 0;
        font-weight: 500;
    }
    .agent-card {
        background: #1e2060;
        border: 1px solid #2e3080;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 8px;
    }
    .agent-card h3 {
        color: #FFC000 !important;
        font-size: 14px;
        margin: 0 0 4px 0;
    }
    .agent-card p {
        color: #a0a8d0 !important;
        font-size: 12px;
        margin: 0;
    }
    .stChatMessage {
        background-color: #ffffff !important;
        border: 1px solid #dde2ea !important;
        border-radius: 8px !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .stChatMessage p, .stChatMessage span, .stChatMessage li, .stChatMessage td {
        color: #1a1a2e !important;
    }
    .stChatMessage h1, .stChatMessage h2, .stChatMessage h3, .stChatMessage h4 {
        color: #17175D !important;
    }
    .stChatMessage strong {
        color: #17175D !important;
    }
    .stChatMessage code {
        color: #0563C1 !important;
        background-color: #eef1f8 !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
    }
    .stChatMessage pre {
        background-color: #f0f2f6 !important;
        border: 1px solid #d0d5dd !important;
        border-radius: 6px !important;
        padding: 12px !important;
    }
    .stChatMessage pre code {
        color: #1a1a2e !important;
        background-color: transparent !important;
        font-size: 13px !important;
        line-height: 1.5 !important;
    }
    .stChatMessage table {
        border-collapse: collapse !important;
        width: 100% !important;
    }
    .stChatMessage table th,
    .stChatMessage table thead th,
    .stChatMessage table thead tr th,
    .stChatMessage th {
        background-color: #17175D !important;
        color: #ffffff !important;
        padding: 8px 12px !important;
        font-weight: 600 !important;
    }
    .stChatMessage table td {
        padding: 6px 12px !important;
        border-bottom: 1px solid #e2e8f0 !important;
        color: #1a1a2e !important;
    }
    div[data-testid="stChatInput"] textarea {
        background-color: #ffffff !important;
        border: 1px solid #4472C4 !important;
        color: #17175D !important;
        font-size: 14px !important;
    }
    div[data-testid="stChatInput"] textarea::placeholder {
        color: #8890b0 !important;
    }
    .powered-by {
        color: #8890c0;
        font-size: 11px;
        text-align: center;
        padding: 16px;
    }
    .stButton button {
        background-color: #17175D !important;
        color: #FFC000 !important;
        border: 1px solid #4472C4 !important;
        font-weight: 600 !important;
    }
    .stButton button:hover {
        background-color: #0563C1 !important;
        color: #ffffff !important;
    }
    [data-testid="stChatInput"] button {
        background-color: #0563C1 !important;
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
        color: #17175D !important;
    }
    .main .block-container {
        background-color: #f4f6f9;
        border-radius: 8px;
        padding-top: 16px;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.markdown("### Select Agent")

    agent_name = st.radio(
        "Choose an agent:",
        list(AGENTS.keys()),
        label_visibility="collapsed"
    )

    st.markdown("---")

    for name, info in AGENTS.items():
        selected = "border-left: 3px solid #60a5fa;" if name == agent_name else ""
        st.markdown(f"""
        <div class="agent-card" style="{selected}">
            <h3>{name}</h3>
            <p>{info['description']}</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Platform:** Azure AI Foundry")
    st.markdown("**Model:** GPT-4o")
    st.markdown("**Region:** East US")

    if st.button("Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("last_po_json", None)
        st.session_state.pop("last_upload", None)
        st.rerun()

    # --- Dashboard Stats ---
    st.markdown("---")
    st.markdown("### Dashboard")
    s = st.session_state.stats
    total_tokens = s["total_tokens_in"] + s["total_tokens_out"]
    est_cost = (s["total_tokens_in"] * 0.005 + s["total_tokens_out"] * 0.015) / 1000

    st.markdown(f"""
<div style="background: #1e2060; border-radius: 8px; padding: 12px; margin-bottom: 8px;">
<p style="color: #FFC000; font-size: 11px; margin: 0; text-transform: uppercase; font-weight: 700;">Session Stats</p>
<table style="width: 100%; margin-top: 8px;">
<tr><td style="color: #a0a8d0; font-size: 12px; padding: 2px 0;">Queries</td><td style="color: #ffffff; font-size: 12px; text-align: right; padding: 2px 0;">{s['total_queries']}</td></tr>
<tr><td style="color: #a0a8d0; font-size: 12px; padding: 2px 0;">Tokens In</td><td style="color: #ffffff; font-size: 12px; text-align: right; padding: 2px 0;">{s['total_tokens_in']:,}</td></tr>
<tr><td style="color: #a0a8d0; font-size: 12px; padding: 2px 0;">Tokens Out</td><td style="color: #ffffff; font-size: 12px; text-align: right; padding: 2px 0;">{s['total_tokens_out']:,}</td></tr>
<tr><td style="color: #a0a8d0; font-size: 12px; padding: 2px 0;">Est. Cost</td><td style="color: #4ade80; font-size: 12px; text-align: right; padding: 2px 0;">${est_cost:.4f}</td></tr>
</table>
</div>
""", unsafe_allow_html=True)

    if s["agent_queries"]:
        # Agent usage bar chart
        import pandas as pd
        chart_data = {}
        for name, data in s["agent_queries"].items():
            short_name = name[:15]
            chart_data[short_name] = data["tokens_in"] + data["tokens_out"]
        if chart_data:
            df_chart = pd.DataFrame({"Tokens": chart_data})
            st.bar_chart(df_chart, color="#FFC000", height=120)

        st.markdown(f"""
<div style="background: #1e2060; border-radius: 8px; padding: 12px; margin-bottom: 8px;">
<p style="color: #FFC000; font-size: 11px; margin: 0; text-transform: uppercase; font-weight: 700;">By Agent</p>
<table style="width: 100%; margin-top: 8px;">
""" + "".join([
            f'<tr><td style="color: #a0a8d0; font-size: 11px; padding: 2px 0;">{name[:20]}</td><td style="color: #ffffff; font-size: 11px; text-align: right; padding: 2px 0;">{data["queries"]}q / {data["tokens_in"]+data["tokens_out"]:,}t</td></tr>'
            for name, data in s["agent_queries"].items()
        ]) + """
</table>
</div>
""", unsafe_allow_html=True)

    if s["query_log"]:
        recent = s["query_log"][-5:]
        st.markdown(f"""
<div style="background: #1e2060; border-radius: 8px; padding: 12px;">
<p style="color: #FFC000; font-size: 11px; margin: 0; text-transform: uppercase; font-weight: 700;">Recent Activity</p>
""" + "".join([
            f'<p style="color: #a0a8d0; font-size: 10px; margin: 3px 0; font-family: monospace;">{log["time"]} | {log["agent"][:12]} | {log["tokens_in"]+log["tokens_out"]:,}t | {log["latency"]}</p>'
            for log in reversed(recent)
        ]) + """
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="powered-by">Powered by C365<br>Azure AI Platform</div>', unsafe_allow_html=True)

# --- Main Area ---
import base64
import os

header_path = os.path.join(os.path.dirname(__file__), "kiwi_sunset.png")
if os.path.exists(header_path):
    with open(header_path, "rb") as img_file:
        header_b64 = base64.b64encode(img_file.read()).decode()
    st.markdown(f"""
<div style="position: relative; border-radius: 10px; overflow: hidden; margin-bottom: 16px; max-height: 120px;">
    <img src="data:image/png;base64,{header_b64}" style="width: 100%; display: block; border-radius: 10px; object-fit: cover; height: 120px;">
    <div style="position: absolute; bottom: 10px; left: 20px;">
        <h1 style="color: #ffffff; font-size: 22px; margin: 0; text-shadow: 2px 2px 8px rgba(0,0,0,0.7);">C365 AI Platform</h1>
        <p style="color: #FFC000; font-size: 11px; margin: 2px 0 0 0; text-shadow: 1px 1px 4px rgba(0,0,0,0.7);">Powered by Azure AI</p>
    </div>
</div>
""", unsafe_allow_html=True)
else:
    st.markdown("""
<div class="main-header">
    <h1>C365 AI Platform</h1>
    <p>C365 | Powered by Azure AI</p>
</div>
""", unsafe_allow_html=True)

# --- Chat ---
if "messages" not in st.session_state:
    st.session_state.messages = []

if "current_agent" not in st.session_state:
    st.session_state.current_agent = agent_name

# Reset chat if agent changes
if st.session_state.current_agent != agent_name:
    st.session_state.messages = []
    st.session_state.current_agent = agent_name

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Welcome message
WELCOME_MESSAGES = {
    "P21 PO Import": "**P21 PO Import Agent** ready. Upload a PDF, cXML file, or **paste email text** containing a PO — I'll parse it and push it straight into the P21 database.",
    "Document Intelligence": "**Document Intelligence** ready. Paste text from any document — POs, invoices, spec sheets, packing slips — and I'll extract all structured data from it.",
    "Filtration Sales Mastermind": "**Filtration Sales Mastermind** ready. Ask me about products, pricing, cross-references, chemical compatibility, or say **demo** to see what I can do.",
    "Customer Service Agent": "**Customer Service Agent** ready. Paste any customer email — order inquiries, complaints, returns, pricing questions — and I'll pull up their account in P21, analyze the issue, and draft a professional response.",
    "M365 Integration Agent": "**M365 Integration Agent** ready. Ask me to find documents in SharePoint, search Outlook emails, check Teams messages, review calendar — I search across your entire Microsoft 365 environment.",
    "Emma Robot — RPA": "**Emma Robot RPA** ready. Paste structured order data (JSON) and I'll build the execution plan to type it directly into P21 — no API needed. Emma sees the screen and acts like a human.",
    "Order Processing Agent — Email": "**Order Processing Agent** ready. Paste any order email — freeform, forwarded chains, messy text — and I'll extract a structured Purchase Order from it.",
    "M4 Knick Sales Configurator": "**M4 Knick Sales Configurator** ready. I help you configure complete measurement loops (pH, ORP, conductivity, dissolved oxygen), look up SKUs and specs, cross-reference competitors, and prep for customer meetings. Say **demo** for a walkthrough or **/configure** to build a loop.",
    "Ellsworth Adhesives Mastermind": "**Ellsworth Adhesives Mastermind** ready — your Digital Glue Doctor. I match adhesives to applications, look up specs, cross-reference competitors, calculate coverage, and troubleshoot bonding issues across 65+ manufacturers. Say **demo** for the full tour or describe your bonding challenge. Talk or type. Voice works.",
}
if not st.session_state.messages:
    with st.chat_message("assistant"):
        welcome = WELCOME_MESSAGES.get(agent_name, f"**{agent_name}** ready.")
        st.markdown(welcome)

# File upload for Document Intelligence
if agent_name == "Document Intelligence":
    uploaded_file = st.file_uploader("Upload a document (PDF, TXT, CSV)", type=["pdf", "txt", "csv"], label_visibility="collapsed")
    if uploaded_file is not None and "last_upload" not in st.session_state or (uploaded_file is not None and st.session_state.get("last_upload") != uploaded_file.name):
        st.session_state.last_upload = uploaded_file.name
        if uploaded_file.type == "application/pdf":
            try:
                import fitz
                pdf_bytes = uploaded_file.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                file_text = f"[Uploaded PDF: {uploaded_file.name}]\n\n{text}"
            except Exception as e:
                file_text = f"Error reading PDF: {e}"
        else:
            file_text = f"[Uploaded file: {uploaded_file.name}]\n\n{uploaded_file.read().decode('utf-8', errors='replace')}"

        st.session_state.messages.append({"role": "user", "content": file_text})
        with st.chat_message("user"):
            st.markdown(f"Uploaded: **{uploaded_file.name}**")
        with st.chat_message("assistant"):
            with st.spinner("Extracting document data..."):
                client = AzureOpenAI(azure_endpoint=ENDPOINT, api_key=API_KEY, api_version=API_VERSION)
                messages = [{"role": "system", "content": AGENTS[agent_name]["system_prompt"]}]
                for msg in st.session_state.messages:
                    messages.append({"role": msg["role"], "content": msg["content"]})
                t0 = time.time()
                response = client.chat.completions.create(model=MODEL, messages=messages, temperature=0.1)
                track_usage(agent_name, response, time.time() - t0)
                reply = response.choices[0].message.content
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
                json_match = re.search(r'```json\s*(.*?)\s*```', reply, re.DOTALL)
                if json_match:
                    try:
                        st.session_state.last_po_json = json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        pass
        st.rerun()

# --- P21 PO Import Agent ---
if agent_name == "P21 PO Import":
    import sys
    import glob as glob_mod
    import tempfile
    import pyodbc
    import pandas as pd
    sys.path.insert(0, r'C:\Claude\Tools')

    P21_CONN_STR = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={st.secrets.get('SQL_SERVER', 'sintonia-p21-dev.database.windows.net')};DATABASE={st.secrets.get('SQL_DATABASE', 'p21_sandbox')};UID={st.secrets.get('SQL_USERNAME', 'sintoniaadmin')};PWD={st.secrets.get('SQL_PASSWORD', 'Sandbox2026')}"
    PO_INBOX_DIR = os.path.join(os.path.dirname(__file__), 'inbox')
    os.makedirs(PO_INBOX_DIR, exist_ok=True)

    st.markdown("---")
    p21_tab1, p21_tab2, p21_tab3, p21_tab4 = st.tabs(["📥 PO Inbox", "📄 Import PO", "📦 PO Dashboard", "📊 Audit Log"])

    # ============ TAB 1: PO INBOX ============
    with p21_tab1:
        st.subheader("PO Inbox")
        st.caption("Auto-forwarded POs from Ariba, Coupa, and email land here. Process with one click.")

        # Scan inbox folder
        inbox_files = []
        for ext_pat in ['*.pdf', '*.xml', '*.txt', '*.cxml', '*.eml', '*.msg']:
            inbox_files.extend(glob_mod.glob(os.path.join(PO_INBOX_DIR, ext_pat)))
        inbox_files.sort(key=os.path.getmtime, reverse=True)

        # Check staging table for already-processed POs
        processed_pos = set()
        try:
            p21_conn = pyodbc.connect(P21_CONN_STR)
            staging_df = pd.read_sql("SELECT DISTINCT po_no FROM dbo.po_import_staging WHERE status IN ('IMPORTED', 'DUPLICATE')", p21_conn)
            processed_pos = set(staging_df['po_no'].tolist())
            p21_conn.close()
        except:
            pass

        if inbox_files:
            st.markdown(f"**{len(inbox_files)} file(s) in inbox**")
            for idx, fpath in enumerate(inbox_files):
                fname = os.path.basename(fpath)
                fsize = os.path.getsize(fpath)
                fmod = datetime.fromtimestamp(os.path.getmtime(fpath))
                ext = os.path.splitext(fname)[1].lower()

                # Determine file type icon
                if ext == '.pdf':
                    icon = "📄"
                    ftype = "PDF"
                elif ext in ('.xml', '.cxml', '.txt'):
                    icon = "📋"
                    ftype = "cXML"
                else:
                    icon = "📧"
                    ftype = "Email"

                with st.container():
                    col_icon, col_info, col_actions = st.columns([0.5, 4, 2])
                    with col_icon:
                        st.markdown(f"<div style='font-size: 28px; text-align: center; padding-top: 8px;'>{icon}</div>", unsafe_allow_html=True)
                    with col_info:
                        st.markdown(f"**{fname}**")
                        st.caption(f"{ftype} | {fsize:,} bytes | Received: {fmod.strftime('%Y-%m-%d %H:%M')}")
                    with col_actions:
                        bcol1, bcol2 = st.columns(2)
                        with bcol1:
                            if st.button("🔍 Preview", key=f"inbox_preview_{idx}", use_container_width=True):
                                with st.spinner(f"Parsing {fname}..."):
                                    try:
                                        if ext == '.pdf':
                                            from ariba_p21_agent import parse_pdf
                                            header, lines, raw = parse_pdf(fpath)
                                        else:
                                            from ariba_p21_agent import parse_cxml
                                            header, lines, raw = parse_cxml(fpath)
                                        st.session_state['p21_header'] = header
                                        st.session_state['p21_lines'] = lines
                                        st.session_state['p21_raw'] = raw
                                        st.success(f"PO {header.get('po_no', 'N/A')} | {len(lines)} lines | ${header.get('total_amt', 0):,.2f}")
                                    except Exception as e:
                                        st.error(f"Parse error: {e}")
                        with bcol2:
                            if st.button("🚀 Import", key=f"inbox_import_{idx}", type="primary", use_container_width=True):
                                with st.spinner(f"Importing {fname} to P21..."):
                                    try:
                                        if ext == '.pdf':
                                            from ariba_p21_agent import parse_pdf, import_to_p21
                                            header, lines, raw = parse_pdf(fpath)
                                        else:
                                            from ariba_p21_agent import parse_cxml, import_to_p21
                                            header, lines, raw = parse_cxml(fpath)
                                        result = import_to_p21(header, lines, raw)
                                        if result['status'] == 'IMPORTED':
                                            st.success(f"✅ IMPORTED — PO {result['po_no']} | {result['lines']} lines | ${result['total']:,.2f}")
                                            # Move to processed subfolder
                                            processed_dir = os.path.join(PO_INBOX_DIR, 'Processed')
                                            os.makedirs(processed_dir, exist_ok=True)
                                            import shutil
                                            shutil.move(fpath, os.path.join(processed_dir, fname))
                                            st.balloons()
                                        elif result['status'] == 'DUPLICATE':
                                            st.warning(f"⚠️ PO {result['po_no']} already exists.")
                                    except Exception as e:
                                        st.error(f"Import error: {e}")
                    st.markdown("---")
        else:
            st.info("📭 Inbox is empty. Drop PO files (PDF, cXML, email) into:")
            st.code(PO_INBOX_DIR)
            st.caption("Tip: Set up an Outlook rule to auto-save Ariba/Coupa PO attachments to this folder.")

        # Show parsed preview if available
        if 'p21_header' in st.session_state and st.session_state.get('p21_header'):
            h = st.session_state['p21_header']
            st.subheader("Preview")
            c1, c2, c3 = st.columns(3)
            c1.metric("PO Number", h.get('po_no', 'N/A'))
            c2.metric("Total", f"${h.get('total_amt', 0):,.2f}")
            c3.metric("Lines", len(st.session_state.get('p21_lines', [])))
            st.markdown(f"**Supplier:** {h.get('supplier_name', 'N/A')} | **Ship To:** {h.get('ship2_name', 'N/A')} | **Buyer:** {h.get('buyer', 'N/A')}")
            if st.session_state.get('p21_lines'):
                lines_df = pd.DataFrame(st.session_state['p21_lines'])
                st.dataframe(lines_df, use_container_width=True, hide_index=True)

    # ============ TAB 2: IMPORT PO ============
    with p21_tab2:
        st.subheader("Import a Purchase Order")
        p21_method = st.radio("Input Method:", ["Upload File (PDF/cXML)", "Paste Email Text"], horizontal=True, key="p21_method")

        if p21_method == "Upload File (PDF/cXML)":
            p21_file = st.file_uploader("Upload PO file", type=['pdf', 'xml', 'txt', 'cxml'], key="p21_upload")
            if p21_file:
                ext = os.path.splitext(p21_file.name)[1].lower()
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(p21_file.getvalue())
                    tmp_path = tmp.name
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔍 Parse Only (Preview)", key="p21_parse", use_container_width=True):
                        with st.spinner("Parsing..."):
                            try:
                                if ext == '.pdf':
                                    from ariba_p21_agent import parse_pdf
                                    header, lines, raw = parse_pdf(tmp_path)
                                else:
                                    from ariba_p21_agent import parse_cxml
                                    header, lines, raw = parse_cxml(tmp_path)
                                st.session_state['p21_header'] = header
                                st.session_state['p21_lines'] = lines
                                st.session_state['p21_raw'] = raw
                                st.success(f"Parsed: **{p21_file.name}** → PO {header.get('po_no', 'N/A')} | {len(lines)} lines | ${header.get('total_amt', 0):,.2f}")
                            except Exception as e:
                                st.error(f"Parse error: {e}")
                with col2:
                    if st.button("🚀 Parse & Push to SQL", key="p21_import", type="primary", use_container_width=True):
                        with st.spinner("Importing to P21..."):
                            try:
                                if ext == '.pdf':
                                    from ariba_p21_agent import parse_pdf, import_to_p21
                                    header, lines, raw = parse_pdf(tmp_path)
                                else:
                                    from ariba_p21_agent import parse_cxml, import_to_p21
                                    header, lines, raw = parse_cxml(tmp_path)
                                result = import_to_p21(header, lines, raw)
                                if result['status'] == 'IMPORTED':
                                    st.success(f"✅ **IMPORTED** — PO {result['po_no']} | {result['lines']} lines | ${result['total']:,.2f}")
                                    st.balloons()
                                elif result['status'] == 'DUPLICATE':
                                    st.warning(f"⚠️ PO {result['po_no']} already exists.")
                            except Exception as e:
                                st.error(f"Import error: {e}")
                try:
                    os.unlink(tmp_path)
                except:
                    pass

        elif p21_method == "Paste Email Text":
            email_text = st.text_area("Paste the email or PO text here:", height=250, key="p21_email_text",
                                      placeholder="Paste the full email containing the PO — cXML, plain text, forwarded chain, anything...")
            if email_text:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🔍 Extract PO from Email", key="p21_email_parse", use_container_width=True):
                        with st.spinner("Extracting PO data..."):
                            try:
                                if '<cXML' in email_text or '<OrderRequest' in email_text:
                                    with tempfile.NamedTemporaryFile(delete=False, suffix='.xml', mode='w', encoding='utf-8') as tmp:
                                        tmp.write(email_text)
                                        tmp_path = tmp.name
                                    from ariba_p21_agent import parse_cxml
                                    header, lines, raw = parse_cxml(tmp_path)
                                    os.unlink(tmp_path)
                                    st.session_state['p21_header'] = header
                                    st.session_state['p21_lines'] = lines
                                    st.session_state['p21_raw'] = raw
                                    st.success(f"cXML detected! PO {header.get('po_no', 'N/A')} | {len(lines)} lines | ${header.get('total_amt', 0):,.2f}")
                                else:
                                    client = AzureOpenAI(azure_endpoint=ENDPOINT, api_key=API_KEY, api_version=API_VERSION)
                                    extract_prompt = """Extract ALL purchase order data from this email text. Return a JSON object with:
{"po_no":"","order_date":"","supplier_name":"","buyer":"","buyer_email":"","ship2_name":"","ship2_add1":"","ship2_city":"","ship2_state":"","ship2_zip":"","bill_to_name":"","terms":"","total_amt":0,"comments":"","lines":[{"line_no":10,"item_description":"","mfg_part_no":"","mfg_name":"","qty_ordered":0,"unit_price":0,"date_due":""}]}
Be precise. If a field is missing, use empty string or 0. Extract EVERY line item."""
                                    t0 = time.time()
                                    response = client.chat.completions.create(
                                        model=MODEL,
                                        messages=[{"role": "system", "content": extract_prompt}, {"role": "user", "content": email_text}],
                                        temperature=0.1
                                    )
                                    track_usage(agent_name, response, time.time() - t0)
                                    reply = response.choices[0].message.content
                                    json_match = re.search(r'```json\s*(.*?)\s*```', reply, re.DOTALL)
                                    data = json.loads(json_match.group(1)) if json_match else json.loads(reply)
                                    st.session_state['p21_header'] = {k: v for k, v in data.items() if k != 'lines'}
                                    st.session_state['p21_lines'] = data.get('lines', [])
                                    st.session_state['p21_raw'] = email_text
                                    h = st.session_state['p21_header']
                                    st.success(f"Extracted: PO {h.get('po_no', 'N/A')} | {len(st.session_state['p21_lines'])} lines | ${h.get('total_amt', 0):,.2f}")
                            except Exception as e:
                                st.error(f"Extraction error: {e}")
                with col2:
                    if st.button("🚀 Extract & Push to SQL", key="p21_email_import", type="primary", use_container_width=True):
                        with st.spinner("Extracting and importing..."):
                            try:
                                if '<cXML' in email_text or '<OrderRequest' in email_text:
                                    with tempfile.NamedTemporaryFile(delete=False, suffix='.xml', mode='w', encoding='utf-8') as tmp:
                                        tmp.write(email_text)
                                        tmp_path = tmp.name
                                    from ariba_p21_agent import parse_cxml, import_to_p21
                                    header, lines, raw = parse_cxml(tmp_path)
                                    os.unlink(tmp_path)
                                else:
                                    client = AzureOpenAI(azure_endpoint=ENDPOINT, api_key=API_KEY, api_version=API_VERSION)
                                    extract_prompt = """Extract ALL purchase order data from this email. Return ONLY JSON (no markdown):
{"po_no":"","order_date":"","supplier_name":"","buyer":"","buyer_email":"","ship2_name":"","ship2_add1":"","ship2_city":"","ship2_state":"","ship2_zip":"","bill_to_name":"","terms":"","total_amt":0,"comments":"","lines":[{"line_no":10,"item_description":"","mfg_part_no":"","mfg_name":"","qty_ordered":0,"unit_price":0,"date_due":""}]}"""
                                    t0 = time.time()
                                    response = client.chat.completions.create(
                                        model=MODEL,
                                        messages=[{"role": "system", "content": extract_prompt}, {"role": "user", "content": email_text}],
                                        temperature=0.1
                                    )
                                    track_usage(agent_name, response, time.time() - t0)
                                    reply = response.choices[0].message.content
                                    json_match = re.search(r'```json\s*(.*?)\s*```', reply, re.DOTALL)
                                    data = json.loads(json_match.group(1)) if json_match else json.loads(reply)
                                    header = {k: v for k, v in data.items() if k != 'lines'}
                                    lines = data.get('lines', [])
                                    raw = email_text
                                from ariba_p21_agent import import_to_p21
                                result = import_to_p21(header, lines, raw)
                                if result['status'] == 'IMPORTED':
                                    st.success(f"✅ **IMPORTED** — PO {result['po_no']} | {result['lines']} lines | ${result['total']:,.2f}")
                                    st.balloons()
                                elif result['status'] == 'DUPLICATE':
                                    st.warning(f"⚠️ PO {result['po_no']} already exists.")
                            except Exception as e:
                                st.error(f"Import error: {e}")

        # Preview area for Import tab
        if 'p21_header' in st.session_state and st.session_state.get('p21_header'):
            h = st.session_state['p21_header']
            st.markdown("---")
            st.subheader("Parsed PO Preview")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("PO Number", h.get('po_no', 'N/A'))
            c2.metric("Total", f"${h.get('total_amt', 0):,.2f}")
            c3.metric("Lines", len(st.session_state.get('p21_lines', [])))
            c4.metric("Source", "cXML" if h.get('supplier_name') else "PDF/Email")
            st.markdown(f"**Supplier:** {h.get('supplier_name', 'N/A')} | **Ship To:** {h.get('ship2_name', 'N/A')}, {h.get('ship2_city', '')} {h.get('ship2_state', '')} | **Buyer:** {h.get('buyer', 'N/A')}")
            if st.session_state.get('p21_lines'):
                lines_df = pd.DataFrame(st.session_state['p21_lines'])
                st.dataframe(lines_df, use_container_width=True, hide_index=True)

    # ============ TAB 3: PO DASHBOARD ============
    with p21_tab3:
        st.subheader("POs in P21 Database")
        try:
            p21_conn = pyodbc.connect(P21_CONN_STR)
            po_df = pd.read_sql("""
                SELECT h.po_no AS [PO Number],
                       CONVERT(varchar(10), h.order_date, 120) AS [Order Date],
                       s.supplier_name AS [Supplier],
                       h.ship2_name AS [Ship To],
                       h.buyer AS [Buyer],
                       h.total_amt AS [Total],
                       h.import_source AS [Source],
                       h.import_status AS [Status],
                       (SELECT COUNT(*) FROM dbo.po_line l WHERE l.po_no = h.po_no) AS [Lines]
                FROM dbo.po_hdr h
                LEFT JOIN dbo.supplier s ON s.supplier_id = h.supplier_id
                ORDER BY h.order_date DESC
            """, p21_conn)

            if not po_df.empty:
                # Summary metrics
                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("Total POs", len(po_df))
                mc2.metric("Total Value", f"${po_df['Total'].sum():,.2f}")
                mc3.metric("Total Lines", int(po_df['Lines'].sum()))
                mc4.metric("Suppliers", po_df['Supplier'].nunique())

                po_df['Total'] = po_df['Total'].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "$0.00")
                st.dataframe(po_df, use_container_width=True, hide_index=True)

                # Line item detail
                st.subheader("Line Item Detail")
                po_list = po_df['PO Number'].tolist()
                selected_po = st.selectbox("Select PO:", po_list, key="p21_po_select")
                if selected_po:
                    lines_df = pd.read_sql(f"""
                        SELECT line_no AS [Line], item_description AS [Description],
                               mfg_name AS [Manufacturer], mfg_part_no AS [Mfg Part #],
                               qty_ordered AS [Qty], unit_price AS [Unit Price],
                               CAST(qty_ordered * unit_price AS decimal(18,2)) AS [Extended],
                               CONVERT(varchar(10), date_due, 120) AS [Due Date]
                        FROM dbo.po_line WHERE po_no = '{selected_po}' ORDER BY line_no
                    """, p21_conn)
                    if not lines_df.empty:
                        lines_df['Unit Price'] = lines_df['Unit Price'].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "")
                        lines_df['Extended'] = lines_df['Extended'].apply(lambda x: f"${x:,.2f}" if pd.notnull(x) else "")
                        st.dataframe(lines_df, use_container_width=True, hide_index=True)
            else:
                st.info("No POs imported yet.")
            p21_conn.close()
        except Exception as e:
            st.error(f"Database error: {e}")

    # ============ TAB 4: AUDIT LOG ============
    with p21_tab4:
        st.subheader("Import Staging / Audit Trail")
        try:
            p21_conn = pyodbc.connect(P21_CONN_STR)
            audit_df = pd.read_sql("""
                SELECT staging_id AS [ID], source_system AS [Source], po_no AS [PO],
                       status AS [Status],
                       CONVERT(varchar(19), created_date, 120) AS [Received],
                       CONVERT(varchar(19), processed_date, 120) AS [Processed],
                       error_message AS [Error]
                FROM dbo.po_import_staging ORDER BY staging_id DESC
            """, p21_conn)
            if not audit_df.empty:
                # Status summary
                sc1, sc2, sc3, sc4 = st.columns(4)
                status_counts = audit_df['Status'].value_counts()
                sc1.metric("Imported", status_counts.get('IMPORTED', 0))
                sc2.metric("Parsed", status_counts.get('PARSED', 0))
                sc3.metric("Pending", status_counts.get('PENDING', 0))
                sc4.metric("Errors", status_counts.get('ERROR', 0))
                st.dataframe(audit_df, use_container_width=True, hide_index=True)
            else:
                st.info("No import activity yet.")
            p21_conn.close()
        except Exception as e:
            st.error(f"Database error: {e}")

        # Supplier master
        st.markdown("---")
        st.subheader("Supplier Master")
        try:
            p21_conn = pyodbc.connect(P21_CONN_STR)
            sup_df = pd.read_sql("""
                SELECT supplier_id AS [ID], supplier_name AS [Name],
                       city AS [City], state AS [State], terms_code AS [Terms], active_flag AS [Active]
                FROM dbo.supplier ORDER BY supplier_name
            """, p21_conn)
            st.dataframe(sup_df, use_container_width=True, hide_index=True)
            p21_conn.close()
        except Exception as e:
            st.error(f"Error: {e}")

# Chat input placeholders per agent
PLACEHOLDERS = {
    "P21 PO Import": "Paste email text containing a PO...",
    "Document Intelligence": "Paste document text or upload a file above...",
    "Filtration Sales Mastermind": "Ask about products, pricing, specs, or type 'demo'...",
    "Customer Service Agent": "Paste a customer email...",
    "M365 Integration Agent": "Ask me to find something across M365...",
    "Emma Robot — RPA": "Paste order JSON or say 'demo' to see an execution plan...",
    "Order Processing Agent — Email": "Paste an order email...",
    "M4 Knick Sales Configurator": "Ask about sensors, transmitters, or type '/configure' to build a loop...",
    "Ellsworth Adhesives Mastermind": "Describe your bonding challenge, or type 'demo'...",
}
if prompt := st.chat_input(PLACEHOLDERS.get(agent_name, "Type a message...")):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call Azure OpenAI
    with st.chat_message("assistant"):
        with st.spinner("Processing..."):
            client = AzureOpenAI(
                azure_endpoint=ENDPOINT,
                api_key=API_KEY,
                api_version=API_VERSION,
            )

            messages = [
                {"role": "system", "content": AGENTS[agent_name]["system_prompt"]}
            ]
            # Include chat history for context
            for msg in st.session_state.messages:
                messages.append({"role": msg["role"], "content": msg["content"]})

            t0 = time.time()
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.1
            )
            track_usage(agent_name, response, time.time() - t0)

            reply = response.choices[0].message.content
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})

            # Try to extract JSON from reply for Create PO button
            json_match = re.search(r'```json\s*(.*?)\s*```', reply, re.DOTALL)
            if json_match:
                try:
                    st.session_state.last_po_json = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

# --- Data Validation / Scrub Preview (Feature #2) ---
if "last_po_json" in st.session_state and st.session_state.last_po_json and agent_name == "Order Processing Agent — Email":
    po = st.session_state.last_po_json
    po_num = po.get("po_number") or po.get("order_header", {}).get("po_number", "")
    cust = po.get("customer", {})
    ship = po.get("ship_to", {})
    items = po.get("line_items", [])
    flags = po.get("flags", {})
    missing = flags.get("missing_fields", [])
    confidence = po.get("confidence_score", 0)
    conf_val = float(confidence) if confidence else 0

    checks = []
    checks.append(("PO Number", bool(po_num), po_num or "Missing"))
    checks.append(("Customer Name", bool(cust.get("company")), cust.get("company", "Missing")))
    checks.append(("Contact Info", bool(cust.get("contact_name")), cust.get("contact_name", "Missing")))
    ship_addr = ship.get("full_address") or ship.get("address", "")
    checks.append(("Ship-To Address", bool(ship_addr), ship_addr[:40] + "..." if len(ship_addr) > 40 else (ship_addr or "Missing")))
    checks.append(("Line Items", len(items) > 0, f"{len(items)} items"))
    priced = sum(1 for i in items if i.get("unit_price"))
    checks.append(("All Items Priced", priced == len(items), f"{priced}/{len(items)} priced"))
    checks.append(("AI Confidence", conf_val >= 0.7, f"{conf_val:.0%}" if conf_val else "N/A"))

    pass_count = sum(1 for _, ok, _ in checks if ok)
    total_checks = len(checks)

    if conf_val >= 0.8 and pass_count >= total_checks - 1:
        overall_color = "#22c55e"
        overall_label = "READY FOR IMPORT"
    elif conf_val >= 0.5 and pass_count >= total_checks - 2:
        overall_color = "#f59e0b"
        overall_label = "REVIEW REQUIRED"
    else:
        overall_color = "#ef4444"
        overall_label = "NEEDS ATTENTION"

    st.markdown("---")
    st.markdown(f"""
<div style="background: #ffffff; border: 2px solid {overall_color}; border-radius: 10px; padding: 16px; margin-bottom: 12px;">
<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
<h4 style="color: #17175D; margin: 0;">Data Validation</h4>
<span style="background: {overall_color}; color: #ffffff; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 700;">{overall_label}</span>
</div>
<table style="width: 100%;">
""" + "".join([
        f'<tr><td style="padding: 3px 8px; font-size: 13px; color: #17175D;">{name}</td><td style="padding: 3px 8px; text-align: center;"><span style="color: {"#22c55e" if ok else "#ef4444"}; font-weight: 700;">{"PASS" if ok else "FAIL"}</span></td><td style="padding: 3px 8px; font-size: 12px; color: #64748b;">{detail}</td></tr>'
        for name, ok, detail in checks
    ]) + f"""
</table>
<p style="color: #94a3b8; font-size: 10px; margin: 8px 0 0 0; text-align: right;">{pass_count}/{total_checks} checks passed</p>
</div>""", unsafe_allow_html=True)

    # --- Pipeline View (Feature #4) ---
    steps = [
        ("Email Received", True),
        ("AI Extraction", True),
        ("Data Validation", True),
        ("P21 Import", False),
        ("PO Acknowledgment", False),
    ]
    pipeline_html = '<div style="display: flex; align-items: center; justify-content: center; margin: 8px 0 16px 0; flex-wrap: wrap;">'
    for i, (label, done) in enumerate(steps):
        bg = "#17175D" if done else "#d1d5db"
        txt = "#ffffff" if done else "#6b7280"
        pipeline_html += f'<div style="background: {bg}; color: {txt}; padding: 6px 14px; border-radius: 20px; font-size: 11px; font-weight: 600; white-space: nowrap;">{label}</div>'
        if i < len(steps) - 1:
            pipeline_html += '<div style="color: #9ca3af; margin: 0 4px; font-size: 16px;">→</div>'
    pipeline_html += '</div>'
    st.markdown(pipeline_html, unsafe_allow_html=True)

    # --- Action Buttons ---
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        p21_btn = st.button("Export to P21", use_container_width=True, type="secondary")
    with col2:
        po_btn = st.button("Create Purchase Order", use_container_width=True, type="primary")
    with col3:
        ack_btn = st.button("Send PO Ack Email", use_container_width=True, type="secondary")

    # --- P21 SQL Export ---
    if p21_btn:
        po = st.session_state.last_po_json

        po_num = po.get("po_number") or po.get("order_header", {}).get("po_number", "N/A")
        po_date = po.get("date") or po.get("order_header", {}).get("date", datetime.now().strftime("%Y-%m-%d"))
        po_type = po.get("order_type") or po.get("order_header", {}).get("order_type", "B")
        rush = po.get("rush_order") or po.get("order_header", {}).get("rush_order", "N")

        cust = po.get("customer", {})
        cust_company = cust.get("company", po.get("vendor", ""))
        cust_contact = cust.get("contact_name", "")
        cust_email = cust.get("email", "")
        cust_phone = cust.get("phone", "")

        ship = po.get("ship_to", {})
        ship_name = cust_company
        ship_addr = ship.get("full_address") or ship.get("address", "")
        ship_city = ship.get("city", "")
        ship_state = ship.get("state", "")
        ship_zip = ship.get("zip", "")
        ship_attn = ship.get("attention", "")

        shipping = po.get("shipping", {})
        carrier = shipping.get("carrier", "")
        freight_terms = shipping.get("freight_terms", "")
        ship_acct = shipping.get("account_number", "")

        special = po.get("special_instructions", "")
        delivery = po.get("delivery_date") or po.get("order_header", {}).get("date", "")
        confidence = po.get("confidence_score", "")
        items = po.get("line_items", [])
        flags = po.get("flags", {})
        missing = flags.get("missing_fields", [])
        confirm_needed = flags.get("confirmation_needed", [])

        def sq(val):
            return str(val).replace("'", "''") if val else ""

        rush_flag = "Y" if rush in (True, "Y", "Yes", "yes", True) else "N"

        sql = f"""-- =============================================
-- C365 AI Platform → P21 Order Import
-- Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
-- Source: C365 Order Processing Agent (Azure GPT-4o)
-- AI Confidence: {confidence}
-- =============================================

-- =============================================
-- STEP 1: Insert PO Header → po_hdr
-- Maps to P21 dbo.po_hdr schema
-- =============================================
INSERT INTO dbo.po_hdr (
    po_no,
    order_date,
    po_type,
    company_no,
    ship2_name,
    ship2_add1,
    ship2_city,
    ship2_state,
    ship2_zip,
    carrier_id,
    freight_terms
) VALUES (
    '{sq(po_num)}',                    -- po_no
    '{sq(po_date)}',                   -- order_date
    '{sq(po_type)}',                   -- po_type (B=Buy/Resell, S=Stock, D=Drop Ship)
    1,                                 -- company_no (default)
    '{sq(ship_name)}',                 -- ship2_name
    '{sq(ship_addr)}',                 -- ship2_add1
    '{sq(ship_city)}',                 -- ship2_city
    '{sq(ship_state)}',                -- ship2_state
    '{sq(ship_zip)}',                  -- ship2_zip
    '{sq(carrier)}',                   -- carrier_id
    '{sq(freight_terms)}'              -- freight_terms
);

-- =============================================
-- STEP 2: Insert PO Header Notes → po_hdr_notepad
-- Captures contact info, special instructions, AI flags
-- =============================================
INSERT INTO dbo.po_hdr_notepad (po_no, note) VALUES
('{sq(po_num)}', 'Contact: {sq(cust_contact)} | {sq(cust_email)} | {sq(cust_phone)}');
"""
        if ship_attn:
            sql += f"""INSERT INTO dbo.po_hdr_notepad (po_no, note) VALUES
('{sq(po_num)}', 'Ship To Attn: {sq(ship_attn)}');
"""
        if special:
            sql += f"""INSERT INTO dbo.po_hdr_notepad (po_no, note) VALUES
('{sq(po_num)}', 'Special: {sq(special)}');
"""
        if ship_acct:
            sql += f"""INSERT INTO dbo.po_hdr_notepad (po_no, note) VALUES
('{sq(po_num)}', 'Freight Acct: {sq(ship_acct)}');
"""
        if rush_flag == "Y":
            sql += f"""INSERT INTO dbo.po_hdr_notepad (po_no, note) VALUES
('{sq(po_num)}', '*** RUSH ORDER ***');
"""

        sql += f"""
-- =============================================
-- STEP 3: Insert PO Lines → po_line
-- {len(items)} line items extracted
-- =============================================
"""
        for idx, item in enumerate(items):
            sku = item.get("item_id") or item.get("sku", "")
            desc = item.get("description", "")
            qty = item.get("quantity", 0)
            uom = item.get("uom", "EA")
            unit_p = item.get("unit_price")
            ext_p = item.get("extended_price")
            price_sql = f"{unit_p}" if unit_p else "NULL  -- *** PRICE MISSING - NEEDS REVIEW ***"
            req_date = delivery or "NULL"
            req_date_sql = f"'{sq(req_date)}'" if delivery else "NULL"

            sql += f"""INSERT INTO dbo.po_line (
    po_no, line_no, item_description, extended_desc,
    unit_of_measure, qty_ordered, unit_price,
    required_date, expedite_flag
) VALUES (
    '{sq(po_num)}', {idx + 1}, '{sq(desc)}', '{sq(sku)}',
    '{sq(uom)}', {qty}, {price_sql},
    {req_date_sql}, '{rush_flag}'
);
"""
            # Add line note if price needs confirmation
            if not unit_p:
                sql += f"""INSERT INTO dbo.po_line_notepad (po_no, line_no, note) VALUES
('{sq(po_num)}', {idx + 1}, 'AI FLAG: Price not provided in source email — needs manual pricing');
"""

        # AI validation flags
        if missing or confirm_needed:
            sql += """
-- =============================================
-- AI VALIDATION FLAGS
-- Review these before approving import
-- =============================================
"""
        if missing:
            for m in missing:
                sql += f"-- MISSING: {m}\n"
        if confirm_needed:
            for c in confirm_needed:
                sql += f"-- CONFIRM: {c}\n"

        sql += f"""
-- =============================================
-- STEP 4: Verify Import
-- =============================================
SELECT h.po_no, h.order_date, h.po_type, h.ship2_name,
       l.line_no, l.item_description, l.qty_ordered,
       l.unit_price, l.required_date, l.expedite_flag
FROM dbo.po_hdr h
JOIN dbo.po_line l ON l.po_no = h.po_no
WHERE h.po_no = '{sq(po_num)}'
ORDER BY l.line_no;
"""

        st.markdown("### P21 SQL Import")
        st.code(sql, language="sql")

        review_items = [i for i in items if not i.get("unit_price")]
        if review_items:
            st.warning(f"{len(review_items)} line(s) flagged for price review")
        st.success(f"P21 import generated — {len(items)} lines → po_hdr + po_line + notepad")

    # --- Create PO ---
    if po_btn:
            po = st.session_state.last_po_json

            # Extract fields safely
            po_num = po.get("po_number") or po.get("order_header", {}).get("po_number", "N/A")
            po_date = po.get("date") or po.get("order_header", {}).get("date", datetime.now().strftime("%Y-%m-%d"))

            # Customer
            cust = po.get("customer", {})
            cust_company = cust.get("company", po.get("vendor", "N/A"))
            cust_contact = cust.get("contact_name", "N/A")
            cust_email = cust.get("email", "")
            cust_phone = cust.get("phone", "")

            # Ship to
            ship = po.get("ship_to", {})
            ship_addr = ship.get("full_address") or ship.get("address", "")
            ship_city = ship.get("city", "")
            ship_state = ship.get("state", "")
            ship_zip = ship.get("zip", "")
            ship_attn = ship.get("attention", "")
            if ship_city and ship_state:
                ship_full = f"{ship_addr}, {ship_city}, {ship_state} {ship_zip}".strip()
            elif ship_addr:
                ship_full = ship_addr
            else:
                ship_full = "N/A"

            # Line items
            items = po.get("line_items", [])

            # Shipping
            shipping = po.get("shipping", {})
            carrier = shipping.get("carrier", "N/A")
            service = shipping.get("service", "")

            # Special
            special = po.get("special_instructions", "None")
            delivery = po.get("delivery_date", po.get("order_header", {}).get("date", ""))

            # Subtotal
            subtotal = po.get("subtotal", 0)
            if not subtotal and items:
                subtotal = sum(i.get("extended_price", 0) or 0 for i in items)

            # Build PO using Streamlit native components
            st.markdown("---")

            # Header
            hcol1, hcol2 = st.columns([3, 1])
            with hcol1:
                st.markdown(f"""
<div style="border-bottom: 3px solid #17175D; padding-bottom: 12px;">
<h2 style="color: #17175D; margin: 0;">PURCHASE ORDER</h2>
<p style="color: #44546A; font-size: 12px; margin: 2px 0 0 0;">C365 | AI Platform</p>
</div>""", unsafe_allow_html=True)
            with hcol2:
                st.markdown(f"""
<div style="text-align: right; padding-top: 8px;">
<p style="color: #17175D; margin: 0; font-size: 16px;"><strong>PO # {po_num}</strong></p>
<p style="color: #44546A; margin: 2px 0 0 0; font-size: 13px;">Date: {po_date}</p>
</div>""", unsafe_allow_html=True)

            st.markdown("")

            # Customer / Ship To
            ccol1, ccol2 = st.columns(2)
            with ccol1:
                st.markdown(f"""
<div style="background: #eef1f8; padding: 16px; border-radius: 8px; border-left: 4px solid #17175D;">
<p style="color: #0563C1; font-size: 11px; text-transform: uppercase; font-weight: 700; margin: 0 0 6px 0;">Customer</p>
<p style="color: #17175D; margin: 0; font-size: 15px; font-weight: 600;">{cust_company}</p>
<p style="color: #17175D; margin: 2px 0; font-size: 13px;">{cust_contact}</p>
<p style="color: #44546A; margin: 2px 0; font-size: 12px;">{cust_email}</p>
<p style="color: #44546A; margin: 2px 0; font-size: 12px;">{cust_phone}</p>
</div>""", unsafe_allow_html=True)
            with ccol2:
                attn_line = f'<p style="color: #17175D; margin: 2px 0; font-size: 13px;">Attn: {ship_attn}</p>' if ship_attn else ""
                st.markdown(f"""
<div style="background: #eef1f8; padding: 16px; border-radius: 8px; border-left: 4px solid #0563C1;">
<p style="color: #0563C1; font-size: 11px; text-transform: uppercase; font-weight: 700; margin: 0 0 6px 0;">Ship To</p>
<p style="color: #17175D; margin: 0; font-size: 14px;">{ship_full}</p>
{attn_line}
</div>""", unsafe_allow_html=True)

            st.markdown("")

            # Line items table
            import pandas as pd
            rows = []
            for idx, item in enumerate(items):
                sku = item.get("item_id") or item.get("sku", "N/A")
                desc = item.get("description", "N/A")
                qty = item.get("quantity", 0)
                uom = item.get("uom", "EA")
                unit_p = item.get("unit_price")
                ext_p = item.get("extended_price")
                rows.append({
                    "Line": idx + 1,
                    "Item ID": sku,
                    "Description": desc,
                    "Qty": qty,
                    "UOM": uom,
                    "Unit Price": f"${unit_p:,.2f}" if unit_p else "TBD",
                    "Extended": f"${ext_p:,.2f}" if ext_p else "TBD",
                })

            if rows:
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)

            # Total
            st.markdown(f"""
<div style="text-align: right; margin: 8px 0 16px 0;">
<span style="background: #17175D; color: #FFC000; padding: 10px 24px; border-radius: 8px; font-size: 18px; font-weight: 700;">
TOTAL: ${subtotal:,.2f}
</span>
</div>""", unsafe_allow_html=True)

            # Shipping + Delivery
            scol1, scol2 = st.columns(2)
            with scol1:
                st.markdown(f"""
<p style="color: #0563C1; font-size: 11px; text-transform: uppercase; font-weight: 700; margin: 0 0 4px 0;">Shipping</p>
<p style="color: #17175D; font-size: 13px; margin: 0;">{carrier} {service}</p>""", unsafe_allow_html=True)
            with scol2:
                st.markdown(f"""
<p style="color: #0563C1; font-size: 11px; text-transform: uppercase; font-weight: 700; margin: 0 0 4px 0;">Delivery</p>
<p style="color: #17175D; font-size: 13px; margin: 0;">{delivery or 'TBD'}</p>""", unsafe_allow_html=True)

            # Special instructions
            if special and special != "None":
                st.markdown(f"""
<div style="background: #fff8e1; border: 1px solid #FFC000; border-radius: 8px; padding: 12px; margin-top: 16px;">
<p style="color: #b45309; font-size: 11px; text-transform: uppercase; font-weight: 700; margin: 0 0 4px 0;">Special Instructions</p>
<p style="color: #78350f; font-size: 13px; margin: 0;">{special}</p>
</div>""", unsafe_allow_html=True)

            # Footer
            st.markdown("""
<div style="text-align: center; margin-top: 20px; padding-top: 12px; border-top: 1px solid #dde2ea;">
<p style="color: #94a3b8; font-size: 11px; margin: 0;">Generated by C365 AI Platform | Azure AI Foundry</p>
</div>""", unsafe_allow_html=True)

            st.success("Purchase Order created successfully.")

    # --- PO Acknowledgment Email (Feature #1) ---
    if ack_btn:
        po = st.session_state.last_po_json
        po_num = po.get("po_number") or po.get("order_header", {}).get("po_number", "N/A")
        po_date = po.get("date") or po.get("order_header", {}).get("date", datetime.now().strftime("%Y-%m-%d"))
        cust = po.get("customer", {})
        cust_company = cust.get("company", po.get("vendor", "N/A"))
        cust_contact = cust.get("contact_name", "Customer")
        cust_email = cust.get("email", "")
        items = po.get("line_items", [])
        ship = po.get("ship_to", {})
        ship_addr = ship.get("full_address") or ship.get("address", "")
        ship_city = ship.get("city", "")
        ship_state = ship.get("state", "")
        ship_zip = ship.get("zip", "")
        if ship_city and ship_state:
            ship_full = f"{ship_addr}, {ship_city}, {ship_state} {ship_zip}".strip()
        elif ship_addr:
            ship_full = ship_addr
        else:
            ship_full = "On file"
        delivery = po.get("delivery_date") or po.get("order_header", {}).get("date", "TBD")
        shipping_info = po.get("shipping", {})
        carrier = shipping_info.get("carrier", "")
        special = po.get("special_instructions", "")

        # Build line items table for email
        items_table = ""
        for idx, item in enumerate(items):
            sku = item.get("item_id") or item.get("sku", "")
            desc = item.get("description", "")
            qty = item.get("quantity", 0)
            uom = item.get("uom", "EA")
            unit_p = item.get("unit_price")
            price_str = f"${unit_p:,.2f}" if unit_p else "Quote pending"
            items_table += f"  {idx+1}. {desc}"
            if sku:
                items_table += f" ({sku})"
            items_table += f"\n     Qty: {qty} {uom} | Price: {price_str}\n\n"

        special_line = f"\nSpecial Instructions: {special}\n" if special and special != "None" else ""

        email_text = f"""To: {cust_email or '[customer email]'}
Subject: Order Acknowledgment — PO# {po_num}

{cust_contact},

Thank you for your order. This email confirms we have received and are processing your purchase order.

ORDER DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PO Number:    {po_num}
Order Date:   {po_date}
Customer:     {cust_company}
Ship To:      {ship_full}
Carrier:      {carrier or 'TBD'}
Requested By: {delivery}
{special_line}
LINE ITEMS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{items_table}"""

        # Flag any items without pricing
        unpriced = [i for i in items if not i.get("unit_price")]
        if unpriced:
            email_text += f"NOTE: {len(unpriced)} item(s) require pricing confirmation. Our team will follow up with a formal quote for these items.\n\n"

        email_text += """Your order is being processed and we will notify you of any changes to the expected delivery date. If you have any questions, reply to this email or contact your sales representative.

Thank you for your business.

Best regards,
Sales Support
C365 | Powered by Azure AI"""

        st.markdown("### PO Acknowledgment Email")
        st.code(email_text, language="text")

        # Email action buttons
        ecol1, ecol2 = st.columns(2)
        with ecol1:
            st.info(f"Ready to send to: **{cust_email or 'No email on file'}**")
        with ecol2:
            st.success("Email drafted. Copy and send via Outlook.")
