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
    "Transaction Scanner": {
        "description": "PDF & document extraction — upload POs, invoices, specs, any document",
        "system_prompt": """You are the C365 Transaction Scanner Agent, built by C365 on the Azure AI Platform.

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
        "description": "Robotic Process Automation — triggers screen-level automation into the ERP, ERP, any app",
        "system_prompt": """You are the Emma Robot RPA Integration Agent, built by C365 on the Azure AI Platform.

ROLE: You take structured order data and build a simple, clear execution plan showing how Emma Robot (vision-based RPA) would type it into the ERP screens. Emma reads screens and types like a human — no API needed.

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
    "Transaction Extractor": {
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
    "ERP PO Import": {
        "description": "Import POs directly into the ERP SQL — PDF, cXML, or paste email text",
        "system_prompt": """You are the ERP PO Import Agent, built by C365 on the Azure AI Platform.

ROLE: You help users import purchase orders into Prophet 21 (P21) ERP database. You support three input methods:
1. PDF upload — parsed via Azure Transaction Scanner
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
    "Configuration Mastermind": {
        "description": "Analytical sensor expert — configure measurement loops, lookup SKUs, cross-reference competitors",
        "system_prompt": """You are the Configuration Mastermind, built by C365 on the Azure AI Platform.

ROLE: You help internal sales teams and 14 rep firms configure complete measurement loops, look up products, cross-reference competitors, and prepare for customer meetings. You are an expert in liquid analytical measurement: pH, ORP, conductivity, and dissolved oxygen.

DATA LOOKUP RULES:
1. ALWAYS search the knowledge base below FIRST
2. If a product is found in the knowledge base, use ONLY that data for pricing, specs, availability
3. If NOT found: "This product was not found in the SKU Master. Confirm with your product team for accuracy."
4. NEVER fabricate SKUs, pricing, lead times, or specifications
5. For competitor cross-references, provide best-guess match with disclaimer: "[UNVERIFIED CROSSWALK] — confirm with engineering"

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
- /crossref [competitor part] — Find equivalent product
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
    "Adhesives Mastermind": {
        "description": "Adhesive expert — product matching, spec lookup, cross-references, coverage calculators",
        "system_prompt": """You are the Adhesives Mastermind — The Digital Glue Doctor, built by C365 on the Azure AI Platform.

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
- Show what the distributor carries as equivalent
- Note any performance differences
- Label confidence: [Exact Match] / [Functional Equivalent] / [Similar Chemistry]

KEY DIFFERENTIATOR — ALWAYS MENTION WHEN RELEVANT:
- Distributor owns Fisnar (dispensing robots) — recommend dispensing equipment with adhesive
- Distributor owns KitPackers — custom repackaging available
- Distributor owns ResinLab — custom formulation for unique needs
- Glue Doctors = technical sales engineers who consult, not just sell

KNOWLEDGE BASE:
""" + load_knowledge_dir(ELLSWORTH_DATA_DIR)
    },
    "ERP Invoice Extractor": {
        "description": "Invoice search & export — filter by status, supplier, number. Export to CSV/cXML for Coupa/Ariba",
        "system_prompt": """You are the C365 ERP Invoice Extractor Agent, built by C365 on the Azure AI Platform.

YOUR ROLE:
You help users search, filter, and export invoices from the ERP database. You can look up invoices by number, customer, supplier, status, date range, or amount. You also help format invoices for procurement platforms like Coupa and Ariba (cXML format).

CAPABILITIES:
- Search invoices by any combination of filters
- Show invoice details with line items
- Export invoices to CSV or cXML
- Explain invoice statuses and payment terms
- Help troubleshoot invoice discrepancies

Always be precise with dollar amounts and dates. When showing invoice data, format it in clean tables."""
    },
    "Pricing Mastermind": {
        "description": "Margin optimization, competitive pricing, deal scoring, and pricing strategy",
        "system_prompt": """You are the Pricing Mastermind, built by C365 on the Azure AI Platform.

YOUR ROLE:
You are the margin guardian. You analyze pricing data, historical transactions, competitor intelligence, and market conditions to help sales teams maximize margin without losing deals.

CAPABILITIES:
- Analyze deal profitability — flag low-margin quotes before they go out
- Recommend optimal markup by product category, customer tier, and market segment
- Compare pricing against historical averages — "you sold this at 32% last time, why 18% now?"
- Identify pricing trends — which products are getting squeezed, which have room
- Score deals — green/yellow/red based on margin, volume, customer value
- Suggest upsell opportunities based on the order mix
- Track win/loss rates against pricing decisions

When analyzing pricing, always show the math. Margin percentages, dollar impact, comparison to averages. Make it impossible to ignore."""
    },
    "Account Intelligence": {
        "description": "Customer 360 — order history, buying patterns, churn risk, upsell opportunities, AR aging",
        "system_prompt": """You are the Account Intelligence Agent, built by C365 on the Azure AI Platform.

YOUR ROLE:
You are the customer whisperer. You give sales reps and account managers a complete picture of every customer relationship — what they buy, when they buy, what they SHOULD be buying, and whether they're about to leave.

CAPABILITIES:
- Customer 360 view — order history, AR aging, contact info, communication log
- Buying pattern analysis — seasonal trends, product mix, order frequency
- Churn detection — flag customers whose order frequency is dropping
- Upsell/cross-sell recommendations — "this customer buys valves but never filters — they probably need filters"
- Customer segmentation — A/B/C tiering based on revenue, margin, growth potential
- Relationship health score — combines AR status, order trends, and engagement
- Meeting prep — "you're seeing Koch Nitrogen tomorrow, here's everything you need to know"

Always lead with actionable insights. Don't just show data — tell the rep what to DO about it."""
    },
    "Inventory Mastermind": {
        "description": "Stock optimization, dead stock alerts, reorder intelligence, ABC analysis, demand forecasting",
        "system_prompt": """You are the Inventory Mastermind, built by C365 on the Azure AI Platform.

YOUR ROLE:
You optimize inventory for industrial distributors — the right parts, in the right quantities, at the right locations. You eliminate dead stock, prevent stockouts, and make warehouse managers sleep better at night.

CAPABILITIES:
- ABC analysis — classify inventory by revenue contribution and turn rate
- Dead stock identification — items sitting 180+ days with no movement
- Reorder intelligence — dynamic reorder points based on lead time and demand variability
- Demand forecasting — predict future demand from historical patterns and seasonality
- Stock-to-sales ratio analysis — are you over-invested or under-stocked?
- Supplier lead time tracking — which vendors are reliable, which ones drift
- Transfer recommendations — move slow stock from one branch to where it sells
- Cost analysis — carrying cost, obsolescence risk, opportunity cost of capital

Show dollar impact on everything. "This dead stock is costing you $47K/year in carrying costs" hits different than "you have old inventory." """
    },
    "Proposal Generator": {
        "description": "Turn conversations into branded PDF quotes with pricing, delivery, terms, and follow-up",
        "system_prompt": """You are the Proposal Generator, built by C365 on the Azure AI Platform.

YOUR ROLE:
You are the closer. You take a sales conversation, a parts list, or a customer request and turn it into a professional, branded proposal document — complete with pricing, delivery timelines, terms, and a follow-up cadence.

CAPABILITIES:
- Generate branded PDF proposals from conversational input
- Pull product data, pricing, and availability from the ERP
- Apply customer-specific pricing tiers and discount structures
- Include delivery estimates based on stock availability and supplier lead times
- Add terms and conditions based on customer agreement type
- Track proposal status — sent, viewed, accepted, expired
- Suggest follow-up timing — "this proposal was viewed 3 times but not signed, follow up Thursday"
- Compare proposal versions — what changed between V1 and V2

Output proposals in clean, professional format. Include a summary at the top that a VP can scan in 10 seconds."""
    }
}

# --- Page Config ---
st.set_page_config(
    page_title="C365 AI Platform",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Login Gate ---
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none; }
        header { display: none; }
    </style>
    """, unsafe_allow_html=True)

    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        st.markdown("""
        <div style="text-align: center; margin-top: 60px; margin-bottom: 30px;">
            <div style="background: #FDB813; width: 64px; height: 64px; border-radius: 14px; display: inline-flex; align-items: center; justify-content: center; font-size: 20px; font-weight: 800; color: #0A0B43; margin-bottom: 12px;">C365</div>
            <h1 style="color: #0A0B43; font-size: 28px; margin: 0; font-family: 'Clear Sans', sans-serif;">C365 AI Platform</h1>
            <p style="color: #666; font-size: 14px; margin: 8px 0 0 0;">Powered by Azure AI</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            st.markdown("""
            <div style="background: white; border: 1px solid #e0e4ea; border-radius: 12px; padding: 32px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);">
            """, unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submitted = st.form_submit_button("Sign In", use_container_width=True, type="primary")
            st.markdown("</div>", unsafe_allow_html=True)

            if submitted:
                if username and password:
                    st.session_state.authenticated = True
                    st.session_state.user_name = username
                    st.rerun()
                else:
                    st.error("Please enter username and password.")

        st.markdown("""
        <p style="text-align: center; color: #999; font-size: 11px; margin-top: 24px;">
            Epicor Platinum Elite Partner &nbsp;|&nbsp; Enterprise Technology for Industrial Distribution
        </p>
        """, unsafe_allow_html=True)
    st.stop()

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
        background-color: #0A0B43;
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
        color: #FDB813 !important;
    }
    [data-testid="stSidebar"] .stMarkdown p {
        color: #c0c8e0 !important;
    }
    .main-header {
        background: linear-gradient(135deg, #0A0B43 0%, #1e2878 50%, #0296E5 100%);
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
        color: #FDB813;
        font-size: 14px;
        margin: 4px 0 0 0;
        font-weight: 500;
    }
    .agent-card {
        background: #0e0e3d;
        border: 1px solid #2e3080;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 8px;
    }
    .agent-card h3 {
        color: #FDB813 !important;
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
        color: #0A0B43 !important;
    }
    .stChatMessage strong {
        color: #0A0B43 !important;
    }
    .stChatMessage code {
        color: #0296E5 !important;
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
        background-color: #0A0B43 !important;
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
        color: #0A0B43 !important;
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
        background-color: #0A0B43 !important;
        color: #FDB813 !important;
        border: 1px solid #4472C4 !important;
        font-weight: 600 !important;
    }
    .stButton button:hover {
        background-color: #0296E5 !important;
        color: #ffffff !important;
    }
    [data-testid="stChatInput"] button {
        background-color: #0296E5 !important;
    }
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
        color: #0A0B43 !important;
    }
    .main .block-container {
        background-color: #f4f6f9;
        border-radius: 8px;
        padding-top: 16px;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
AGENT_GROUPS = {
    "Order Processing": ["ERP PO Import", "Transaction Extractor", "Transaction Scanner", "ERP Invoice Extractor"],
    "Sales Intelligence": ["Filtration Sales Mastermind", "Configuration Mastermind", "Adhesives Mastermind"],
    "Operations": ["Emma Robot — RPA", "Customer Service Agent", "M365 Integration Agent"],
    "Next Up": ["Pricing Mastermind", "Account Intelligence", "Inventory Mastermind", "Proposal Generator"],
}

with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 8px 0 12px 0;">
        <div style="background: #FDB813; width: 40px; height: 40px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 800; color: #0A0B43; font-size: 13px;">C365</div>
        <p style="color: #FDB813 !important; font-size: 13px; font-weight: 600; margin: 6px 0 0 0; letter-spacing: 0.5px;">C365 AI Platform</p>
    </div>
    """, unsafe_allow_html=True)

    user_display = st.session_state.get("user_name", "User")
    st.markdown(f"""
    <div style="text-align: center; padding: 4px 0 8px 0;">
        <p style="color: #8890c0 !important; font-size: 11px; margin: 0;">Signed in as <span style="color: #FDB813 !important;">{user_display}</span></p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # Initialize agent selection — None = landing page
    if "selected_agent" not in st.session_state:
        st.session_state.selected_agent = None

    COMING_SOON = {"Pricing Mastermind", "Account Intelligence", "Inventory Mastermind", "Proposal Generator"}

    for group_name, group_agents in AGENT_GROUPS.items():
        if group_name == "Next Up":
            st.markdown("""
            <div style="margin: 20px 0 8px 0; padding-top: 12px; border-top: 1px solid rgba(253,184,19,0.3);">
                <p style="color: #FDB813 !important; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; margin: 0;">&#9889; Next Up</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <p style="color: #FDB813 !important; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; margin: 16px 0 8px 0;">{group_name}</p>
            """, unsafe_allow_html=True)
        for name in group_agents:
            if name in AGENTS:
                if name in COMING_SOON:
                    st.markdown(f"""
                    <div style="background: rgba(253,184,19,0.08); border: 1px dashed #FDB813; border-radius: 6px; padding: 8px 12px; margin-bottom: 4px; display: flex; justify-content: space-between; align-items: center;">
                        <span style="color: #8890c0; font-size: 13px;">{name}</span>
                        <span style="background: linear-gradient(135deg, #FDB813, #f59e0b); color: #0A0B43; font-size: 9px; font-weight: 700; padding: 2px 8px; border-radius: 10px; letter-spacing: 0.5px;">NEXT UP</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    is_selected = name == st.session_state.selected_agent
                    if st.button(
                        name,
                        key=f"agent_btn_{name}",
                        use_container_width=True,
                        type="primary" if is_selected else "secondary"
                    ):
                        st.session_state.selected_agent = name
                        st.session_state.messages = []
                        st.rerun()

    agent_name = st.session_state.selected_agent or list(AGENTS.keys())[0]

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
<div style="background: #0e0e3d; border-radius: 8px; padding: 12px; margin-bottom: 8px;">
<p style="color: #FDB813; font-size: 11px; margin: 0; text-transform: uppercase; font-weight: 700;">Session Stats</p>
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
            st.bar_chart(df_chart, color="#FDB813", height=120)

        st.markdown(f"""
<div style="background: #0e0e3d; border-radius: 8px; padding: 12px; margin-bottom: 8px;">
<p style="color: #FDB813; font-size: 11px; margin: 0; text-transform: uppercase; font-weight: 700;">By Agent</p>
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
<div style="background: #0e0e3d; border-radius: 8px; padding: 12px;">
<p style="color: #FDB813; font-size: 11px; margin: 0; text-transform: uppercase; font-weight: 700;">Recent Activity</p>
""" + "".join([
            f'<p style="color: #a0a8d0; font-size: 10px; margin: 3px 0; font-family: monospace;">{log["time"]} | {log["agent"][:12]} | {log["tokens_in"]+log["tokens_out"]:,}t | {log["latency"]}</p>'
            for log in reversed(recent)
        ]) + """
</div>
""", unsafe_allow_html=True)

    st.markdown("""
    <div class="powered-by">
        <div style="width: 28px; height: 28px; background: #FDB813; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; font-size: 9px; font-weight: 800; color: #0A0B43; margin-bottom: 4px;">C365</div>
        <br>C365<br>Azure AI Platform
    </div>
    """, unsafe_allow_html=True)

# --- Main Area ---
st.markdown("""
<div style="background: linear-gradient(135deg, #0A0B43 0%, #0296E5 50%, #00B4D8 100%); border-radius: 12px; padding: 28px 32px; margin-bottom: 20px; position: relative; overflow: hidden;">
    <div style="position: absolute; top: -20px; right: -20px; width: 200px; height: 200px; background: rgba(253,184,19,0.06); border-radius: 50%;"></div>
    <div style="position: absolute; bottom: -30px; right: 60px; width: 120px; height: 120px; background: rgba(253,184,19,0.04); border-radius: 50%;"></div>
    <div style="display: flex; align-items: center; gap: 16px;">
        <div style="background: #FDB813; width: 52px; height: 52px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 900; color: #0A0B43; flex-shrink: 0;">C365</div>
        <div>
            <h1 style="color: #ffffff; font-size: 26px; margin: 0; font-weight: 700; letter-spacing: -0.5px; font-family: 'Clear Sans', sans-serif;">C365 AI Platform</h1>
            <p style="color: #FDB813; font-size: 12px; margin: 4px 0 0 0; font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase; font-family: 'Clear Sans', sans-serif;">Powered by Azure AI</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- Landing Page ---
if st.session_state.get("selected_agent") is None:
    st.markdown("""
<div style="max-width: 800px; margin: 0 auto;">

<h2 style="color: #0A0B43; text-align: center; margin-bottom: 8px; font-family: 'Clear Sans', sans-serif;">We make <span style="color: #0296E5;">TECHNOLOGY</span> work for industrial distribution.</h2>
<p style="color: #555; text-align: center; font-size: 15px; margin-bottom: 32px;">C365 AI Platform brings intelligent automation to every stage of your distribution workflow — from order processing to invoicing to customer service.</p>

<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;">

<div style="background: white; border: 1px solid #e0e4ea; border-radius: 10px; padding: 20px; border-left: 4px solid #00B4D8;">
<h4 style="color: #0A0B43; margin: 0 0 8px 0; font-size: 15px;">📥 Order Processing</h4>
<p style="color: #555; font-size: 13px; margin: 0;">Import POs from Ariba, Coupa, email, or PDF. AI parses any format and pushes directly into your ERP — no manual entry.</p>
</div>

<div style="background: white; border: 1px solid #e0e4ea; border-radius: 10px; padding: 20px; border-left: 4px solid #FDB813;">
<h4 style="color: #0A0B43; margin: 0 0 8px 0; font-size: 15px;">🔍 Sales Intelligence</h4>
<p style="color: #555; font-size: 13px; margin: 0;">Product experts at your fingertips. Cross-reference parts, check specs, configure measurement loops, and prep for customer meetings.</p>
</div>

<div style="background: white; border: 1px solid #e0e4ea; border-radius: 10px; padding: 20px; border-left: 4px solid #0296E5;">
<h4 style="color: #0A0B43; margin: 0 0 8px 0; font-size: 15px;">📄 Invoice Management</h4>
<p style="color: #555; font-size: 13px; margin: 0;">Search, filter, and export invoices. Generate CSV or cXML for Coupa and Ariba integration. AR aging and payment tracking built in.</p>
</div>

<div style="background: white; border: 1px solid #e0e4ea; border-radius: 10px; padding: 20px; border-left: 4px solid #0A0B43;">
<h4 style="color: #0A0B43; margin: 0 0 8px 0; font-size: 15px;">⚡ Operations & RPA</h4>
<p style="color: #555; font-size: 13px; margin: 0;">Automate screen-level tasks with Emma Robot RPA. Handle customer emails with AI-drafted responses. Search across Microsoft 365.</p>
</div>

</div>

<div style="background: linear-gradient(135deg, #0A0B43, #0296E5); border-radius: 10px; padding: 20px; text-align: center;">
<p style="color: #FDB813; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 4px 0;">Get Started</p>
<p style="color: #ffffff; font-size: 14px; margin: 0;">Select an agent from the sidebar to begin.</p>
</div>

<div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #e0e4ea;">
<p style="color: #94a3b8; font-size: 11px; margin: 0; letter-spacing: 0.5px;">14 AI agents. Zero manual entry. One platform.</p>
<p style="color: #b0b8c4; font-size: 10px; margin: 6px 0 0 0;">Built on Azure AI Foundry &nbsp;|&nbsp; Sinton.ia Architecture</p>
</div>

</div>
""", unsafe_allow_html=True)
    st.stop()

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
    "ERP PO Import": """**ERP PO Import Agent** ready.

**What I do:** I take purchase orders from any source — Ariba cXML, Coupa, PDF documents, or raw email text — and push them directly into your ERP database. No manual entry.

**How to use me:**
- **Upload a file** — drag a PDF or cXML into the PO Inbox tab
- **Paste email text** — copy an order email and paste it in the Import tab
- **Check status** — use the PO Dashboard to see what's been imported

**Supported formats:** PDF, cXML (Ariba/Coupa), plain text email, structured forms

Try uploading a PO or pasting an order email to get started.""",

    "Transaction Scanner": """**Transaction Scanner** ready.

**What I do:** I read any business document — POs, invoices, spec sheets, packing slips, BOMs, contracts — and extract every piece of structured data into clean JSON. I also validate math (line totals, tax calculations, grand totals).

**How to use me:**
- **Paste text** from any document into the chat
- **Upload a PDF** using the file uploader above
- I'll return structured JSON with all extracted fields

**Pro tip:** I catch math errors that humans miss — discrepancies in line totals, tax calculations, and invoice amounts.""",

    "Filtration Sales Mastermind": """**Filtration Sales Mastermind** ready.

**What I do:** I'm your product expert for filtration, instrumentation, and process control. I look up specs, cross-reference competitor parts, check chemical compatibility, and help you find the right solution.

**How to use me:**
- Ask about any product, part number, or application
- Type **demo** to see all my capabilities
- Ask me to cross-reference a competitor part number
- Describe your process conditions and I'll recommend products""",
    "Customer Service Agent": """**Customer Service Agent** ready.

**What I do:** I handle incoming customer emails — complaints, order inquiries, return requests, pricing questions, delivery issues. I look up the customer's account in the ERP, analyze the situation, and draft a professional response.

**How to use me:**
- **Paste a customer email** into the chat
- I'll identify the issue, simulate an ERP lookup, and draft a response
- I handle: order status, returns, complaints, pricing, delivery issues""",

    "M365 Integration Agent": """**M365 Integration Agent** ready.

**What I do:** I search across your entire Microsoft 365 environment — SharePoint documents, Outlook emails, Teams messages, calendar events, and OneDrive files.

**How to use me:**
- Ask me to find any document, email, or conversation
- Search by keyword, sender, date range, or topic
- I search SharePoint, Outlook, Teams, and OneDrive simultaneously""",

    "Emma Robot — RPA": """**Emma Robot RPA** ready.

**What I do:** I take structured order data and build execution plans for screen-level automation. Emma Robot sees the screen and types like a human — no API integration needed.

**How to use me:**
- **Paste structured order data** (JSON) into the chat
- I'll generate a step-by-step execution plan for Emma
- Works with any ERP screen — order entry, receiving, invoicing""",

    "Transaction Extractor": """**Transaction Extractor** ready.

**What I do:** I pull purchase orders out of anything — freeform emails, forwarded chains, text messages, PDFs, screenshots, structured forms. Doesn't matter how messy it is. I find the order and give you clean, structured data.

**How to use me:**
- **Paste any email** — messy, forwarded, informal, doesn't matter
- **Upload a PDF** or paste text from any source
- I'll extract: customer, items, quantities, pricing, ship-to, dates
- Output is ERP-ready structured data, ready for import""",

    "Configuration Mastermind": """**Configuration Mastermind** ready.

**What I do:** I help you configure complete measurement loops — pH, ORP, conductivity, dissolved oxygen, pressure, temperature. I look up SKUs, check specs, cross-reference competitors, and build quotes.

**How to use me:**
- Type **demo** for a full capability walkthrough
- Type **/configure** to build a measurement loop
- Ask about any sensor, transmitter, or analyzer
- Give me a competitor part number and I'll cross-reference it""",
    "Adhesives Mastermind": """**Adhesives Mastermind** ready — your Digital Glue Doctor.

**What I do:** I match adhesives to applications, look up specs, cross-reference competitors, calculate coverage, and troubleshoot bonding issues across 65+ manufacturers. Epoxies, silicones, cyanoacrylates, polyurethanes, hot melts — if it bonds, I know it.

**How to use me:**
- **Describe your application** — substrates, environment, load, cure time requirements
- Type **demo** for a full capability walkthrough
- Ask me to cross-reference a competitor adhesive
- Ask about chemical resistance, temperature ratings, or surface prep

**Coverage:** 65+ manufacturers across epoxies, silicones, cyanoacrylates, polyurethanes, hot melts, UV-cure, and specialty formulations.""",
    "Pricing Mastermind": """**Pricing Mastermind** ready — your margin guardian.

**What I do:** I analyze every deal before it goes out the door. I compare pricing against historical averages, flag low-margin quotes, recommend optimal markup, and score deals green/yellow/red so your team never leaves money on the table.

**How to use me:**
- **Paste a quote or order** — I'll score the margin on every line
- **Ask about a customer's pricing history** — what did you sell this at last time?
- **Compare a deal** — "is 18% margin good for this product category?"
- **Identify margin leakers** — which products or customers are dragging you down

**The goal:** Every deal that leaves this building is priced to win AND priced to profit.""",

    "Account Intelligence": """**Account Intelligence** ready — your customer whisperer.

**What I do:** I give you a complete 360 view of every customer relationship. Order history, buying patterns, AR aging, churn risk, and upsell opportunities. I tell you what to sell, who to call, and when to worry.

**How to use me:**
- **Ask about any customer** — "tell me about Koch Nitrogen"
- **Get meeting prep** — "I'm seeing Exelon tomorrow, what do I need to know?"
- **Find at-risk accounts** — "who hasn't ordered in 90 days?"
- **Spot upsell opportunities** — "who buys valves but not filters?"

**The goal:** No customer falls through the cracks. No upsell gets missed.""",

    "Inventory Mastermind": """**Inventory Mastermind** ready — your stock optimizer.

**What I do:** I analyze your entire inventory position — dead stock eating cash, fast movers running low, reorder points that need adjusting, and demand patterns you haven't noticed. I turn warehouse chaos into working capital.

**How to use me:**
- **Ask for an ABC analysis** — see your inventory ranked by revenue and turn rate
- **Find dead stock** — "what's been sitting 180+ days with no movement?"
- **Check reorder status** — "what needs to be ordered this week?"
- **Forecast demand** — "what will this customer need next quarter based on history?"

**The goal:** Right parts. Right quantities. Right time. Zero dead weight.""",

    "Proposal Generator": """**Proposal Generator** ready — your closer.

**What I do:** I turn sales conversations into professional, branded proposals. Give me a parts list, a customer request, or even a rough email — I'll build a complete quote with pricing, delivery, terms, and follow-up cadence.

**How to use me:**
- **Paste a customer request** — email, text, call notes, anything
- **Build a quote** — "quote 10 pressure switches for Marathon Petroleum, Net 30"
- **Track proposals** — "what quotes are outstanding this week?"
- **Follow up** — "this proposal was viewed 3 times but not signed"

**The goal:** From conversation to signed proposal in minutes, not days.""",

    "ERP Invoice Extractor": """**ERP Invoice Extractor** ready.

**What I do:** I search, filter, and export invoices from the ERP database. I generate CSV and cXML exports for Coupa and Ariba integration. I also show AR aging, payment status, and customer breakdowns.

**How to use me:**
- **Search tab** — filter by status (Open, Paid, Disputed), customer, supplier, or invoice number
- **Detail tab** — enter an invoice number to see full header, addresses, and line items
- **Export tab** — generate CSV or cXML downloads for procurement platforms
- **Dashboard tab** — AR aging, top customers, status summary""",
}
if not st.session_state.messages:
    with st.chat_message("assistant"):
        welcome = WELCOME_MESSAGES.get(agent_name, f"**{agent_name}** ready.")
        st.markdown(welcome)

# File upload for Transaction Scanner
if agent_name == "Transaction Scanner":
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

# --- ERP PO Import Agent ---
if agent_name == "ERP PO Import":
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
                        with st.spinner("Importing to ERP..."):
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
        st.subheader("POs in the ERP Database")
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

# --- ERP Invoice Extractor Agent ---
if agent_name == "ERP Invoice Extractor":
    import pyodbc
    import pandas as pd
    from io import BytesIO

    INV_CONN_STR = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={st.secrets.get('SQL_SERVER', 'sintonia-p21-dev.database.windows.net')};DATABASE={st.secrets.get('SQL_DATABASE', 'p21_sandbox')};UID={st.secrets.get('SQL_USERNAME', 'sintoniaadmin')};PWD={st.secrets.get('SQL_PASSWORD', 'Sandbox2026')}"

    st.markdown("---")
    inv_tab1, inv_tab2, inv_tab3, inv_tab4 = st.tabs(["🔍 Invoice Search", "📄 Invoice Detail", "📤 Export", "📊 Dashboard"])

    # ============ TAB 1: INVOICE SEARCH ============
    with inv_tab1:
        st.subheader("Invoice Search")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filter_status = st.selectbox("Status", ["All", "Open", "Paid", "Partially Paid", "Disputed"], key="inv_status")
        with col2:
            filter_invoice = st.text_input("Invoice #", key="inv_no_filter", placeholder="e.g. 6217000")
        with col3:
            filter_customer = st.text_input("Customer", key="inv_cust_filter", placeholder="Search customer name...")
        with col4:
            filter_supplier = st.text_input("Supplier ID", key="inv_supp_filter", placeholder="e.g. 307609")

        if st.button("🔍 Search Invoices", key="inv_search_btn"):
            try:
                inv_conn = pyodbc.connect(INV_CONN_STR)
                query = """
                    SELECT h.invoice_no, h.invoice_date, h.bill2_name AS customer,
                           h.po_no, h.total_amount, h.tax_amount, h.freight,
                           h.amount_paid, h.invoice_status AS status,
                           h.terms_desc, h.salesrep_name, h.net_due_date,
                           h.supplier_id, h.ship2_name, h.carrier_name
                    FROM dbo.invoice_hdr h
                    WHERE 1=1
                """
                params = []
                if filter_status != "All":
                    query += " AND h.invoice_status = ?"
                    params.append(filter_status)
                if filter_invoice:
                    query += " AND h.invoice_no LIKE ?"
                    params.append(f"%{filter_invoice}%")
                if filter_customer:
                    query += " AND h.bill2_name LIKE ?"
                    params.append(f"%{filter_customer}%")
                if filter_supplier:
                    query += " AND CAST(h.supplier_id AS VARCHAR) = ?"
                    params.append(filter_supplier)
                query += " ORDER BY h.invoice_date DESC"

                df = pd.read_sql(query, inv_conn, params=params)
                inv_conn.close()

                if df.empty:
                    st.info("No invoices found matching your filters.")
                else:
                    st.success(f"**{len(df)} invoice(s) found**")

                    # Summary metrics
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Total Invoices", len(df))
                    m2.metric("Total Amount", f"${df['total_amount'].sum():,.2f}")
                    m3.metric("Amount Paid", f"${df['amount_paid'].sum():,.2f}")
                    m4.metric("Outstanding", f"${(df['total_amount'].sum() - df['amount_paid'].sum()):,.2f}")

                    # Color-code status
                    def color_status(val):
                        colors = {"Open": "#3b82f6", "Paid": "#22c55e", "Partially Paid": "#f59e0b", "Disputed": "#ef4444"}
                        return f'color: {colors.get(val, "#000000")}; font-weight: bold'

                    styled = df.style.applymap(color_status, subset=['status'])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.session_state.inv_search_results = df

            except Exception as e:
                st.error(f"Database error: {e}")

    # ============ TAB 2: INVOICE DETAIL ============
    with inv_tab2:
        st.subheader("Invoice Detail")
        detail_inv_no = st.text_input("Enter Invoice Number:", key="inv_detail_no", placeholder="e.g. 6217000")

        if st.button("📄 Load Invoice", key="inv_detail_btn") and detail_inv_no:
            try:
                inv_conn = pyodbc.connect(INV_CONN_STR)

                # Header
                hdr = pd.read_sql(f"SELECT * FROM dbo.invoice_hdr WHERE invoice_no = ?", inv_conn, params=[detail_inv_no])
                if hdr.empty:
                    st.warning(f"Invoice {detail_inv_no} not found.")
                else:
                    row = hdr.iloc[0]
                    st.markdown(f"### Invoice #{row['invoice_no']}")

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.markdown("**Bill To:**")
                        st.text(f"{row.get('bill2_name', '')}")
                        st.text(f"{row.get('bill2_address1', '')}")
                        st.text(f"{row.get('bill2_city', '')}, {row.get('bill2_state', '')} {row.get('bill2_postal_code', '')}")
                    with c2:
                        st.markdown("**Ship To:**")
                        st.text(f"{row.get('ship2_name', '')}")
                        st.text(f"{row.get('ship2_address1', '')}")
                        st.text(f"{row.get('ship2_city', '')}, {row.get('ship2_state', '')} {row.get('ship2_postal_code', '')}")
                    with c3:
                        st.markdown("**Invoice Info:**")
                        st.text(f"Date: {row.get('invoice_date', '')}")
                        st.text(f"PO: {row.get('po_no', '')}")
                        st.text(f"Terms: {row.get('terms_desc', '')}")
                        st.text(f"Status: {row.get('invoice_status', '')}")
                        st.text(f"Due: {row.get('net_due_date', '')}")

                    # Lines
                    lines = pd.read_sql("""
                        SELECT line_no, item_id, item_desc, qty_shipped, unit_of_measure,
                               unit_price, extended_price
                        FROM dbo.invoice_line WHERE invoice_no = ? ORDER BY line_no
                    """, inv_conn, params=[detail_inv_no])

                    st.markdown("---")
                    st.markdown("**Line Items:**")
                    st.dataframe(lines, use_container_width=True, hide_index=True)

                    # Totals
                    st.markdown("---")
                    t1, t2, t3, t4 = st.columns(4)
                    t1.metric("Subtotal", f"${lines['extended_price'].sum():,.2f}")
                    t2.metric("Tax", f"${float(row.get('tax_amount', 0)):,.2f}")
                    t3.metric("Freight", f"${float(row.get('freight', 0)):,.2f}")
                    t4.metric("Total", f"${float(row.get('total_amount', 0)):,.2f}")

                inv_conn.close()
            except Exception as e:
                st.error(f"Error: {e}")

    # ============ TAB 3: EXPORT ============
    with inv_tab3:
        st.subheader("Export Invoices")
        st.caption("Export invoices to CSV or cXML format for Coupa/Ariba integration.")

        export_status = st.selectbox("Filter by Status:", ["All", "Open", "Paid", "Partially Paid", "Disputed"], key="export_status")
        export_format = st.radio("Export Format:", ["CSV", "cXML (Coupa/Ariba)"], horizontal=True, key="export_fmt")

        if st.button("📤 Generate Export", key="export_btn"):
            try:
                inv_conn = pyodbc.connect(INV_CONN_STR)
                query = """
                    SELECT h.invoice_no, h.invoice_date, h.customer_id, h.bill2_name,
                           h.po_no, h.order_no, h.total_amount, h.tax_amount, h.freight,
                           h.terms_desc, h.net_due_date, h.invoice_status,
                           h.ship2_name, h.ship2_address1, h.ship2_city, h.ship2_state, h.ship2_postal_code,
                           h.bill2_address1, h.bill2_city, h.bill2_state, h.bill2_postal_code,
                           h.salesrep_name, h.carrier_name, h.supplier_id
                    FROM dbo.invoice_hdr h
                    WHERE 1=1
                """
                params = []
                if export_status != "All":
                    query += " AND h.invoice_status = ?"
                    params.append(export_status)
                query += " ORDER BY h.invoice_no"

                hdr_df = pd.read_sql(query, inv_conn, params=params)
                lines_df = pd.read_sql("SELECT * FROM dbo.invoice_line ORDER BY invoice_no, line_no", inv_conn)
                inv_conn.close()

                if hdr_df.empty:
                    st.warning("No invoices to export.")
                else:
                    if export_format == "CSV":
                        # Merge header + lines
                        merged = lines_df.merge(hdr_df, on='invoice_no', how='inner', suffixes=('_line', '_hdr'))
                        csv_data = merged.to_csv(index=False)
                        st.download_button(
                            label=f"⬇️ Download CSV ({len(hdr_df)} invoices, {len(merged)} lines)",
                            data=csv_data,
                            file_name=f"invoices_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                        st.success(f"CSV ready: {len(hdr_df)} invoices, {len(merged)} line items")
                        st.dataframe(hdr_df[['invoice_no', 'bill2_name', 'total_amount', 'invoice_status', 'po_no']], use_container_width=True, hide_index=True)

                    else:
                        # cXML export
                        cxml_parts = []
                        cxml_parts.append('<?xml version="1.0" encoding="UTF-8"?>')
                        cxml_parts.append('<!DOCTYPE cXML SYSTEM "http://xml.cxml.org/schemas/cXML/1.2.061/InvoiceDetail.dtd">')

                        for _, inv in hdr_df.iterrows():
                            inv_lines = lines_df[lines_df['invoice_no'] == inv['invoice_no']]
                            cxml_parts.append(f'<cXML payloadID="{inv["invoice_no"]}@c365" timestamp="{datetime.now().isoformat()}">')
                            cxml_parts.append('  <Header>')
                            cxml_parts.append('    <From><Credential domain="DUNS"><Identity>C365-CLIENT</Identity></Credential></From>')
                            cxml_parts.append(f'    <To><Credential domain="DUNS"><Identity>{inv.get("customer_id", "")}</Identity></Credential></To>')
                            cxml_parts.append('    <Sender><Credential domain="C365"><Identity>C365-Platform</Identity></Credential></Sender>')
                            cxml_parts.append('  </Header>')
                            cxml_parts.append('  <Request>')
                            cxml_parts.append('    <InvoiceDetailRequest>')
                            cxml_parts.append(f'      <InvoiceDetailRequestHeader invoiceID="{inv["invoice_no"]}" invoiceDate="{inv["invoice_date"]}" purpose="standard" operation="new">')
                            cxml_parts.append(f'        <InvoiceDetailHeaderIndicator isHeaderInvoice="yes" />')
                            cxml_parts.append(f'        <InvoicePartner><Contact role="billTo"><Name>{inv.get("bill2_name", "")}</Name>')
                            cxml_parts.append(f'          <PostalAddress><Street>{inv.get("bill2_address1", "")}</Street><City>{inv.get("bill2_city", "")}</City><State>{inv.get("bill2_state", "")}</State><PostalCode>{inv.get("bill2_postal_code", "")}</PostalCode></PostalAddress>')
                            cxml_parts.append(f'        </Contact></InvoicePartner>')
                            cxml_parts.append(f'        <PaymentTerm payInNumberOfDays="{inv.get("terms_desc", "30")}" />')
                            cxml_parts.append(f'      </InvoiceDetailRequestHeader>')

                            for _, line in inv_lines.iterrows():
                                cxml_parts.append(f'      <InvoiceDetailOrder>')
                                cxml_parts.append(f'        <InvoiceDetailOrderInfo><OrderReference orderID="{inv.get("po_no", "")}" /></InvoiceDetailOrderInfo>')
                                cxml_parts.append(f'        <InvoiceDetailItem invoiceLineNumber="{line["line_no"]}" quantity="{line["qty_shipped"]}">')
                                cxml_parts.append(f'          <UnitOfMeasure>{line.get("unit_of_measure", "EA")}</UnitOfMeasure>')
                                cxml_parts.append(f'          <UnitPrice><Money currency="USD">{line["unit_price"]}</Money></UnitPrice>')
                                cxml_parts.append(f'          <InvoiceDetailItemReference lineNumber="{line["line_no"]}">')
                                cxml_parts.append(f'            <ItemID><SupplierPartID>{line.get("item_id", "")}</SupplierPartID></ItemID>')
                                cxml_parts.append(f'            <Description>{line.get("item_desc", "")}</Description>')
                                cxml_parts.append(f'          </InvoiceDetailItemReference>')
                                cxml_parts.append(f'          <SubtotalAmount><Money currency="USD">{line["extended_price"]}</Money></SubtotalAmount>')
                                cxml_parts.append(f'        </InvoiceDetailItem>')
                                cxml_parts.append(f'      </InvoiceDetailOrder>')

                            cxml_parts.append(f'      <InvoiceDetailSummary>')
                            cxml_parts.append(f'        <SubtotalAmount><Money currency="USD">{inv_lines["extended_price"].sum()}</Money></SubtotalAmount>')
                            cxml_parts.append(f'        <Tax><Money currency="USD">{inv.get("tax_amount", 0)}</Money><Description>Tax</Description></Tax>')
                            cxml_parts.append(f'        <ShippingAmount><Money currency="USD">{inv.get("freight", 0)}</Money></ShippingAmount>')
                            cxml_parts.append(f'        <GrossAmount><Money currency="USD">{inv["total_amount"]}</Money></GrossAmount>')
                            cxml_parts.append(f'        <DueAmount><Money currency="USD">{inv["total_amount"] - inv["amount_paid"]}</Money></DueAmount>')
                            cxml_parts.append(f'      </InvoiceDetailSummary>')
                            cxml_parts.append('    </InvoiceDetailRequest>')
                            cxml_parts.append('  </Request>')
                            cxml_parts.append('</cXML>')
                            cxml_parts.append('')

                        cxml_output = "\n".join(cxml_parts)
                        st.download_button(
                            label=f"⬇️ Download cXML ({len(hdr_df)} invoices)",
                            data=cxml_output,
                            file_name=f"invoices_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.cxml",
                            mime="application/xml"
                        )
                        st.success(f"cXML ready: {len(hdr_df)} invoices")
                        st.code(cxml_output[:2000] + "\n..." if len(cxml_output) > 2000 else cxml_output, language="xml")

            except Exception as e:
                st.error(f"Export error: {e}")

    # ============ TAB 4: DASHBOARD ============
    with inv_tab4:
        st.subheader("Invoice Dashboard")
        try:
            inv_conn = pyodbc.connect(INV_CONN_STR)

            # Status summary
            status_df = pd.read_sql("""
                SELECT invoice_status AS Status, COUNT(*) AS Count,
                       SUM(total_amount) AS Total_Amount,
                       SUM(amount_paid) AS Amount_Paid,
                       SUM(total_amount - amount_paid) AS Outstanding
                FROM dbo.invoice_hdr
                GROUP BY invoice_status
            """, inv_conn)

            st.markdown("**By Status:**")
            st.dataframe(status_df, use_container_width=True, hide_index=True)

            # By customer
            cust_df = pd.read_sql("""
                SELECT TOP 10 bill2_name AS Customer, COUNT(*) AS Invoices,
                       SUM(total_amount) AS Total_Amount,
                       SUM(total_amount - amount_paid) AS Outstanding
                FROM dbo.invoice_hdr
                GROUP BY bill2_name
                ORDER BY SUM(total_amount) DESC
            """, inv_conn)

            st.markdown("**Top Customers:**")
            st.dataframe(cust_df, use_container_width=True, hide_index=True)

            # Aging
            aging_df = pd.read_sql("""
                SELECT
                    CASE
                        WHEN invoice_status = 'Paid' THEN 'Paid'
                        WHEN DATEDIFF(day, net_due_date, GETDATE()) <= 0 THEN 'Current'
                        WHEN DATEDIFF(day, net_due_date, GETDATE()) BETWEEN 1 AND 30 THEN '1-30 Past Due'
                        WHEN DATEDIFF(day, net_due_date, GETDATE()) BETWEEN 31 AND 60 THEN '31-60 Past Due'
                        ELSE '60+ Past Due'
                    END AS Aging_Bucket,
                    COUNT(*) AS Count,
                    SUM(total_amount - amount_paid) AS Outstanding
                FROM dbo.invoice_hdr
                GROUP BY
                    CASE
                        WHEN invoice_status = 'Paid' THEN 'Paid'
                        WHEN DATEDIFF(day, net_due_date, GETDATE()) <= 0 THEN 'Current'
                        WHEN DATEDIFF(day, net_due_date, GETDATE()) BETWEEN 1 AND 30 THEN '1-30 Past Due'
                        WHEN DATEDIFF(day, net_due_date, GETDATE()) BETWEEN 31 AND 60 THEN '31-60 Past Due'
                        ELSE '60+ Past Due'
                    END
                ORDER BY Outstanding DESC
            """, inv_conn)

            st.markdown("**AR Aging:**")
            st.dataframe(aging_df, use_container_width=True, hide_index=True)

            inv_conn.close()
        except Exception as e:
            st.error(f"Dashboard error: {e}")

# Chat input placeholders per agent
PLACEHOLDERS = {
    "ERP PO Import": "Paste email text containing a PO...",
    "Transaction Scanner": "Paste document text or upload a file above...",
    "Filtration Sales Mastermind": "Ask about products, pricing, specs, or type 'demo'...",
    "Customer Service Agent": "Paste a customer email...",
    "M365 Integration Agent": "Ask me to find something across M365...",
    "Emma Robot — RPA": "Paste order JSON or say 'demo' to see an execution plan...",
    "Transaction Extractor": "Paste an order email...",
    "Configuration Mastermind": "Ask about sensors, transmitters, or type '/configure' to build a loop...",
    "Adhesives Mastermind": "Describe your bonding challenge, or type 'demo'...",
    "ERP Invoice Extractor": "Search by invoice #, customer, status, or ask a question...",
    "Pricing Mastermind": "Paste a quote, ask about margin, or say 'score this deal'...",
    "Account Intelligence": "Ask about any customer, or say 'who needs attention?'...",
    "Inventory Mastermind": "Ask about stock levels, dead stock, or say 'ABC analysis'...",
    "Proposal Generator": "Paste a customer request or say 'build a quote for...'",
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
if "last_po_json" in st.session_state and st.session_state.last_po_json and agent_name == "Transaction Extractor":
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
<h4 style="color: #0A0B43; margin: 0;">Data Validation</h4>
<span style="background: {overall_color}; color: #ffffff; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 700;">{overall_label}</span>
</div>
<table style="width: 100%;">
""" + "".join([
        f'<tr><td style="padding: 3px 8px; font-size: 13px; color: #0A0B43;">{name}</td><td style="padding: 3px 8px; text-align: center;"><span style="color: {"#22c55e" if ok else "#ef4444"}; font-weight: 700;">{"PASS" if ok else "FAIL"}</span></td><td style="padding: 3px 8px; font-size: 12px; color: #64748b;">{detail}</td></tr>'
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
        ("ERP Import", False),
        ("PO Acknowledgment", False),
    ]
    pipeline_html = '<div style="display: flex; align-items: center; justify-content: center; margin: 8px 0 16px 0; flex-wrap: wrap;">'
    for i, (label, done) in enumerate(steps):
        bg = "#0A0B43" if done else "#d1d5db"
        txt = "#ffffff" if done else "#6b7280"
        pipeline_html += f'<div style="background: {bg}; color: {txt}; padding: 6px 14px; border-radius: 20px; font-size: 11px; font-weight: 600; white-space: nowrap;">{label}</div>'
        if i < len(steps) - 1:
            pipeline_html += '<div style="color: #9ca3af; margin: 0 4px; font-size: 16px;">→</div>'
    pipeline_html += '</div>'
    st.markdown(pipeline_html, unsafe_allow_html=True)

    # --- Action Buttons ---
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        p21_btn = st.button("Export to ERP", use_container_width=True, type="secondary")
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
<div style="border-bottom: 3px solid #0A0B43; padding-bottom: 12px;">
<h2 style="color: #0A0B43; margin: 0;">PURCHASE ORDER</h2>
<p style="color: #44546A; font-size: 12px; margin: 2px 0 0 0;">C365 | AI Platform</p>
</div>""", unsafe_allow_html=True)
            with hcol2:
                st.markdown(f"""
<div style="text-align: right; padding-top: 8px;">
<p style="color: #0A0B43; margin: 0; font-size: 16px;"><strong>PO # {po_num}</strong></p>
<p style="color: #44546A; margin: 2px 0 0 0; font-size: 13px;">Date: {po_date}</p>
</div>""", unsafe_allow_html=True)

            st.markdown("")

            # Customer / Ship To
            ccol1, ccol2 = st.columns(2)
            with ccol1:
                st.markdown(f"""
<div style="background: #eef1f8; padding: 16px; border-radius: 8px; border-left: 4px solid #0A0B43;">
<p style="color: #0296E5; font-size: 11px; text-transform: uppercase; font-weight: 700; margin: 0 0 6px 0;">Customer</p>
<p style="color: #0A0B43; margin: 0; font-size: 15px; font-weight: 600;">{cust_company}</p>
<p style="color: #0A0B43; margin: 2px 0; font-size: 13px;">{cust_contact}</p>
<p style="color: #44546A; margin: 2px 0; font-size: 12px;">{cust_email}</p>
<p style="color: #44546A; margin: 2px 0; font-size: 12px;">{cust_phone}</p>
</div>""", unsafe_allow_html=True)
            with ccol2:
                attn_line = f'<p style="color: #0A0B43; margin: 2px 0; font-size: 13px;">Attn: {ship_attn}</p>' if ship_attn else ""
                st.markdown(f"""
<div style="background: #eef1f8; padding: 16px; border-radius: 8px; border-left: 4px solid #0296E5;">
<p style="color: #0296E5; font-size: 11px; text-transform: uppercase; font-weight: 700; margin: 0 0 6px 0;">Ship To</p>
<p style="color: #0A0B43; margin: 0; font-size: 14px;">{ship_full}</p>
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
<span style="background: #0A0B43; color: #FDB813; padding: 10px 24px; border-radius: 8px; font-size: 18px; font-weight: 700;">
TOTAL: ${subtotal:,.2f}
</span>
</div>""", unsafe_allow_html=True)

            # Shipping + Delivery
            scol1, scol2 = st.columns(2)
            with scol1:
                st.markdown(f"""
<p style="color: #0296E5; font-size: 11px; text-transform: uppercase; font-weight: 700; margin: 0 0 4px 0;">Shipping</p>
<p style="color: #0A0B43; font-size: 13px; margin: 0;">{carrier} {service}</p>""", unsafe_allow_html=True)
            with scol2:
                st.markdown(f"""
<p style="color: #0296E5; font-size: 11px; text-transform: uppercase; font-weight: 700; margin: 0 0 4px 0;">Delivery</p>
<p style="color: #0A0B43; font-size: 13px; margin: 0;">{delivery or 'TBD'}</p>""", unsafe_allow_html=True)

            # Special instructions
            if special and special != "None":
                st.markdown(f"""
<div style="background: #fff8e1; border: 1px solid #FDB813; border-radius: 8px; padding: 12px; margin-top: 16px;">
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
