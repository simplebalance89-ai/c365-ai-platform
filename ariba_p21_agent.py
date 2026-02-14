"""
Ariba/Coupa → P21 Import Agent
Parses cXML and PDF purchase orders and inserts into P21 sandbox database.

Flow:
  1. Detect file type (cXML or PDF)
  2. cXML: Parse directly | PDF: Send to Azure Document Intelligence
  3. Extract header + line items
  4. Stage raw payload in po_import_staging
  5. Insert parsed data into po_hdr + po_line
  6. Return confirmation with PO summary

Usage:
  python ariba_p21_agent.py <file>        (cXML or PDF - auto-detected)
  python ariba_p21_agent.py --test        (re-parse existing cXML sample)
  python ariba_p21_agent.py --test-pdf    (parse Brittany PDF sample)
  python ariba_p21_agent.py --verify <po> (verify imported PO)
"""

import sys
import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime
import pyodbc

# Try Streamlit secrets first, fall back to hardcoded for local CLI use
try:
    import streamlit as st
    SERVER = st.secrets["SQL_SERVER"]
    DATABASE = st.secrets["SQL_DATABASE"]
    USERNAME = st.secrets["SQL_USERNAME"]
    PASSWORD = st.secrets["SQL_PASSWORD"]
    DOC_INTEL_ENDPOINT = st.secrets["DOC_INTEL_ENDPOINT"]
    DOC_INTEL_KEY = st.secrets["DOC_INTEL_KEY"]
except Exception:
    SERVER = 'sintonia-p21-dev.database.windows.net'
    DATABASE = 'p21_sandbox'
    USERNAME = 'sintoniaadmin'
    PASSWORD = 'Sandbox2026'
    DOC_INTEL_ENDPOINT = 'https://eastus.api.cognitive.microsoft.com/'
    DOC_INTEL_KEY = 'BfafFela8VzIMCSjuNbnWAYnV216OHY9EKHELLECbbTvdVNiUir0JQQJ99CBACYeBjFXJ3w3AAALACOGJj67'

DRIVER = '{ODBC Driver 17 for SQL Server}'

def get_connection():
    conn_str = f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};UID={USERNAME};PWD={PASSWORD}'
    return pyodbc.connect(conn_str)

def parse_pdf(file_path):
    """Parse PO PDF using Azure Document Intelligence prebuilt invoice model."""
    from azure.ai.formrecognizer import DocumentAnalysisClient
    from azure.core.credentials import AzureKeyCredential

    client = DocumentAnalysisClient(
        endpoint=DOC_INTEL_ENDPOINT,
        credential=AzureKeyCredential(DOC_INTEL_KEY)
    )

    with open(file_path, 'rb') as f:
        poller = client.begin_analyze_document('prebuilt-invoice', f)
    result = poller.result()

    if not result.documents:
        raise ValueError(f"No invoice/PO data found in {file_path}")

    doc = result.documents[0]
    fields = doc.fields

    def _field_val(name, default=''):
        f = fields.get(name)
        if f is None:
            return default
        if f.value_type == 'currency':
            return f.value.amount if f.value else 0
        return f.value if f.value else (f.content if f.content else default)

    # Build header
    header = {
        'po_no': str(_field_val('PurchaseOrder') or _field_val('InvoiceId', '')),
        'order_date': '',
        'total_amt': _field_val('InvoiceTotal', 0),
        'currency': 'USD',
    }

    # Date
    inv_date = fields.get('InvoiceDate')
    if inv_date and inv_date.value:
        header['order_date'] = str(inv_date.value)[:10]

    # Vendor
    vendor = fields.get('VendorName')
    if vendor:
        header['supplier_name'] = vendor.value or vendor.content or ''
    vendor_addr = fields.get('VendorAddress')
    if vendor_addr and vendor_addr.value:
        addr = vendor_addr.value
        header['supplier_address'] = addr.street_address or ''
        header['supplier_city'] = addr.city or ''
        header['supplier_state'] = addr.state or ''

    # Ship To / Customer
    customer = fields.get('CustomerName')
    if customer:
        header['ship2_name'] = customer.value or customer.content or ''
    cust_addr = fields.get('CustomerAddress')
    if cust_addr and cust_addr.value:
        addr = cust_addr.value
        header['ship2_add1'] = addr.street_address or ''
        header['ship2_city'] = addr.city or ''
        header['ship2_state'] = addr.state or ''
        header['ship2_zip'] = addr.postal_code or ''

    # Bill To
    bill_addr = fields.get('BillingAddress')
    if bill_addr and bill_addr.value:
        addr = bill_addr.value
        header['bill_to_name'] = _field_val('BillingAddressRecipient', '')
        header['bill_to_add1'] = addr.street_address or ''
        header['bill_to_city'] = addr.city or ''
        header['bill_to_state'] = addr.state or ''
        header['bill_to_zip'] = addr.postal_code or ''

    # Ship To from ShippingAddress
    ship_addr = fields.get('ShippingAddress')
    if ship_addr and ship_addr.value:
        addr = ship_addr.value
        if not header.get('ship2_name'):
            header['ship2_name'] = _field_val('ShippingAddressRecipient', '')
        header['ship2_add1'] = addr.street_address or ''
        header['ship2_city'] = addr.city or ''
        header['ship2_state'] = addr.state or ''
        header['ship2_zip'] = addr.postal_code or ''

    # Terms
    header['terms'] = str(_field_val('PaymentTerm', ''))

    # Line items
    lines = []
    items_field = fields.get('Items')
    if items_field and items_field.value:
        for i, item in enumerate(items_field.value):
            item_fields = item.value if item.value else {}
            line = {
                'line_no': (i + 1) * 10,
                'item_description': '',
                'qty_ordered': 1,
                'unit_price': 0,
                'unit_of_measure': 'EA',
                'date_due': header.get('order_date', ''),
            }

            desc = item_fields.get('Description')
            if desc:
                line['item_description'] = desc.value or desc.content or ''

            qty = item_fields.get('Quantity')
            if qty and qty.value:
                line['qty_ordered'] = float(qty.value)

            price = item_fields.get('UnitPrice')
            if price and price.value:
                line['unit_price'] = price.value.amount if hasattr(price.value, 'amount') else float(price.value)

            amount = item_fields.get('Amount')
            if amount and amount.value:
                amt = amount.value.amount if hasattr(amount.value, 'amount') else float(amount.value)
                if line['unit_price'] == 0 and line['qty_ordered'] > 0:
                    line['unit_price'] = amt / line['qty_ordered']

            prod_code = item_fields.get('ProductCode')
            if prod_code:
                line['supplier_part_id'] = prod_code.value or prod_code.content or ''

            uom = item_fields.get('Unit')
            if uom and uom.value:
                line['unit_of_measure'] = uom.value

            date_f = item_fields.get('Date')
            if date_f and date_f.value:
                line['date_due'] = str(date_f.value)[:10]

            lines.append(line)

    # Raw content for staging
    raw_text = result.content[:8000] if result.content else ''

    return header, lines, raw_text


def parse_cxml(file_path):
    """Parse Ariba cXML OrderRequest into structured dict."""
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Get raw XML for staging
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_xml = f.read()

    # Find OrderRequestHeader
    orh = root.find('.//OrderRequestHeader')
    if orh is None:
        raise ValueError("No OrderRequestHeader found in cXML")

    # Header fields
    header = {
        'po_no': orh.get('orderID'),
        'order_date': orh.get('orderDate', '')[:10],  # Extract date portion
        'order_type': orh.get('orderType', 'regular'),
        'total_amt': float(orh.find('.//Total/Money').text) if orh.find('.//Total/Money') is not None else 0,
        'currency': orh.find('.//Total/Money').get('currency', 'USD') if orh.find('.//Total/Money') is not None else 'USD',
    }

    # Ship To
    ship_to = orh.find('.//ShipTo/Address')
    if ship_to is not None:
        header['ship2_name'] = _get_text(ship_to, 'Name')
        postal = ship_to.find('.//PostalAddress')
        if postal is not None:
            header['ship2_add1'] = _get_text(postal, 'Street')
            header['ship2_city'] = _get_text(postal, 'City')
            header['ship2_state'] = _get_text(postal, 'State')
            header['ship2_zip'] = _get_text(postal, 'PostalCode')

    # Bill To
    bill_to = orh.find('.//BillTo/Address')
    if bill_to is not None:
        header['bill_to_name'] = _get_text(bill_to, 'Name')
        postal = bill_to.find('.//PostalAddress')
        if postal is not None:
            header['bill_to_add1'] = _get_text(postal, 'Street')
            header['bill_to_city'] = _get_text(postal, 'City')
            header['bill_to_state'] = _get_text(postal, 'State')
            header['bill_to_zip'] = _get_text(postal, 'PostalCode')

    # Buyer / Purchasing Agent
    buyer_contact = orh.find('.//Contact[@role="purchasingAgent"]')
    if buyer_contact is not None:
        header['buyer'] = _get_text(buyer_contact, 'Name')
        header['buyer_email'] = _get_text(buyer_contact, 'Email')
        phone = buyer_contact.find('.//TelephoneNumber')
        if phone is not None:
            area = _get_text(phone, 'AreaOrCityCode')
            number = _get_text(phone, 'Number')
            header['buyer_phone'] = f"{area}-{number}" if area else number

    # Delivery Terms
    tod = orh.find('.//TermsOfDelivery/TransportTerms')
    if tod is not None:
        header['freight_terms'] = tod.get('value', '') + ' - ' + (tod.text or '')

    # Payment Terms (from Extrinsic)
    for ext in orh.findall('Extrinsic'):
        if ext.get('name') == 'AribaNetwork.PaymentTermsExplanation':
            header['terms'] = ext.text

    # Comments
    comments = orh.find('Comments')
    if comments is not None:
        header['comments'] = (comments.text or '').strip()

    # Supplier info (from To/Correspondent)
    correspondent = root.find('.//To/Correspondent/Contact')
    if correspondent is not None:
        header['supplier_name'] = _get_text(correspondent, 'Name')
        header['supplier_email'] = _get_text(correspondent, 'Email')

    # Line Items
    lines = []
    for item_out in root.findall('.//ItemOut'):
        line = {
            'line_no': int(item_out.get('lineNumber', '0')),
            'qty_ordered': float(item_out.get('quantity', '0')),
            'date_due': item_out.get('requestedDeliveryDate', '')[:10],
        }

        # Item ID
        item_id = item_out.find('.//ItemID')
        if item_id is not None:
            line['supplier_part_id'] = _get_text(item_id, 'SupplierPartID')
            line['buyer_part_id'] = _get_text(item_id, 'BuyerPartID')

        # Item Detail
        detail = item_out.find('.//ItemDetail')
        if detail is not None:
            price_money = detail.find('.//UnitPrice/Money')
            if price_money is not None:
                line['unit_price'] = float(price_money.text)

            line['item_description'] = _get_text(detail, 'Description')
            line['unit_of_measure'] = _get_text(detail, 'UnitOfMeasure') or 'EA'

            mfg_part = detail.find('ManufacturerPartID')
            if mfg_part is not None:
                line['mfg_part_no'] = mfg_part.text

            mfg_name = detail.find('ManufacturerName')
            if mfg_name is not None:
                line['mfg_name'] = mfg_name.text

            # Commodity code
            for cls in detail.findall('Classification'):
                if cls.get('domain') == 'ERPCommodityCode':
                    line['commodity_code'] = cls.text

        # Line comments
        line_comments = item_out.find('Comments')
        if line_comments is not None:
            line['notes'] = (line_comments.text or '').strip()

        lines.append(line)

    return header, lines, raw_xml


def _get_text(element, tag):
    """Safely get text from child element."""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    # Check with namespace
    for child in element:
        if child.tag.endswith(tag) and child.text:
            return child.text.strip()
    return ''


def import_to_p21(header, lines, raw_xml):
    """Insert parsed PO into P21 sandbox database."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 1. Stage raw payload
        parsed_json = json.dumps({
            'header': header,
            'lines': [{k: v for k, v in l.items()} for l in lines]
        }, default=str, indent=2)

        cursor.execute("""
            INSERT INTO dbo.po_import_staging (source_system, raw_payload, parsed_json, po_no, status)
            VALUES (?, ?, ?, ?, 'PARSED')
        """, 'ARIBA', raw_xml[:8000], parsed_json, header.get('po_no'))

        # 2. Check if PO already exists
        cursor.execute("SELECT COUNT(*) FROM dbo.po_hdr WHERE po_no = ?", header.get('po_no'))
        if cursor.fetchone()[0] > 0:
            # Update staging status
            cursor.execute("""
                UPDATE dbo.po_import_staging
                SET status = 'DUPLICATE', error_message = 'PO already exists in po_hdr'
                WHERE po_no = ? AND status = 'PARSED'
            """, header.get('po_no'))
            conn.commit()
            return {'status': 'DUPLICATE', 'po_no': header.get('po_no'), 'message': 'PO already exists'}

        # 3. Resolve supplier_id (or create)
        supplier_id = _resolve_supplier(cursor, header)

        # 4. Insert PO Header
        cursor.execute("""
            INSERT INTO dbo.po_hdr (
                po_no, order_date, po_type, source_type, supplier_id,
                ship2_name, ship2_add1, ship2_city, ship2_state, ship2_zip,
                buyer, buyer_email, buyer_phone,
                terms, freight_terms, total_amt,
                bill_to_name, bill_to_add1, bill_to_city, bill_to_state, bill_to_zip,
                comments, created_by, import_source, import_status
            ) VALUES (?, ?, 'B', 949, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, 1, 'ARIBA', 'IMPORTED')
        """,
            header.get('po_no'),
            header.get('order_date'),
            supplier_id,
            header.get('ship2_name', ''),
            header.get('ship2_add1', ''),
            header.get('ship2_city', ''),
            header.get('ship2_state', ''),
            header.get('ship2_zip', ''),
            header.get('buyer', ''),
            header.get('buyer_email', ''),
            header.get('buyer_phone', ''),
            header.get('terms', ''),
            header.get('freight_terms', ''),
            header.get('total_amt', 0),
            header.get('bill_to_name', ''),
            header.get('bill_to_add1', ''),
            header.get('bill_to_city', ''),
            header.get('bill_to_state', ''),
            header.get('bill_to_zip', ''),
            header.get('comments', '')
        )

        # 5. Insert PO Lines
        for line in lines:
            cursor.execute("""
                INSERT INTO dbo.po_line (
                    po_no, line_no, item_id, item_description,
                    mfg_part_no, mfg_name, unit_of_measure,
                    qty_ordered, unit_price, date_due,
                    buyer_part_id, commodity_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                header.get('po_no'),
                line.get('line_no', 0),
                line.get('supplier_part_id', 'NOT AVAILABLE'),
                line.get('item_description', ''),
                line.get('mfg_part_no', ''),
                line.get('mfg_name', ''),
                line.get('unit_of_measure', 'EA'),
                line.get('qty_ordered', 0),
                line.get('unit_price', 0),
                line.get('date_due'),
                line.get('buyer_part_id', ''),
                line.get('commodity_code', '')
            )

        # 6. Add import note
        cursor.execute("""
            INSERT INTO dbo.po_hdr_notepad (po_no, note)
            VALUES (?, ?)
        """, header.get('po_no'),
            f"Auto-imported from Ariba Network on {datetime.now().strftime('%Y-%m-%d %H:%M')}. "
            f"Buyer: {header.get('buyer', 'Unknown')}. "
            f"Ship to: {header.get('ship2_name', 'Unknown')}, {header.get('ship2_city', '')}, {header.get('ship2_state', '')}."
        )

        # 7. Update staging status
        cursor.execute("""
            UPDATE dbo.po_import_staging
            SET status = 'IMPORTED', processed_date = GETDATE()
            WHERE po_no = ? AND status = 'PARSED'
        """, header.get('po_no'))

        conn.commit()

        return {
            'status': 'IMPORTED',
            'po_no': header.get('po_no'),
            'supplier': header.get('supplier_name', 'Unknown'),
            'ship_to': header.get('ship2_name', ''),
            'total': header.get('total_amt', 0),
            'lines': len(lines),
            'buyer': header.get('buyer', ''),
        }

    except Exception as e:
        conn.rollback()
        # Log error to staging
        try:
            cursor.execute("""
                UPDATE dbo.po_import_staging
                SET status = 'ERROR', error_message = ?
                WHERE po_no = ? AND status = 'PARSED'
            """, str(e), header.get('po_no'))
            conn.commit()
        except:
            pass
        raise

    finally:
        conn.close()


def _resolve_supplier(cursor, header):
    """Find or create supplier from PO header data."""
    supplier_name = header.get('supplier_name', '')

    # Try to find by name
    cursor.execute("SELECT supplier_id FROM dbo.supplier WHERE supplier_name LIKE ?", f'%{supplier_name[:20]}%')
    row = cursor.fetchone()
    if row:
        return row[0]

    # Auto-create with next available ID
    cursor.execute("SELECT ISNULL(MAX(supplier_id), 999999) + 1 FROM dbo.supplier")
    new_id = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO dbo.supplier (supplier_id, supplier_name, email, active_flag)
        VALUES (?, ?, ?, 'Y')
    """, new_id, supplier_name, header.get('supplier_email', ''))

    return new_id


def verify_import(po_no):
    """Read back imported PO to verify."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT h.po_no, h.order_date, s.supplier_name, h.ship2_name,
               h.buyer, h.buyer_email, h.total_amt, h.import_source, h.import_status
        FROM dbo.po_hdr h
        LEFT JOIN dbo.supplier s ON s.supplier_id = h.supplier_id
        WHERE h.po_no = ?
    """, po_no)
    hdr = cursor.fetchone()

    cursor.execute("""
        SELECT line_no, item_description, mfg_part_no, mfg_name,
               qty_ordered, unit_price, CAST(qty_ordered * unit_price AS decimal(18,2)) as extended,
               date_due
        FROM dbo.po_line
        WHERE po_no = ?
        ORDER BY line_no
    """, po_no)
    lines = cursor.fetchall()

    conn.close()

    if hdr:
        print(f"\n{'='*60}")
        print(f"  PO IMPORT VERIFICATION")
        print(f"{'='*60}")
        print(f"  PO Number:    {hdr[0]}")
        print(f"  Order Date:   {str(hdr[1])[:10]}")
        print(f"  Supplier:     {hdr[2]}")
        print(f"  Ship To:      {hdr[3]}")
        print(f"  Buyer:        {hdr[4]} ({hdr[5]})")
        print(f"  Total:        ${hdr[6]:,.2f}")
        print(f"  Source:       {hdr[7]}")
        print(f"  Status:       {hdr[8]}")
        print(f"{'='*60}")
        print(f"  LINE ITEMS ({len(lines)} lines)")
        print(f"{'='*60}")
        for l in lines:
            print(f"  Line {l[0]:>3}: {l[1][:45]:<45}")
            print(f"           Mfg: {l[3]} | Part: {l[2]}")
            print(f"           Qty: {l[4]} x ${l[5]:,.2f} = ${l[6]:,.2f} | Due: {str(l[7])[:10]}")
            print()
        print(f"{'='*60}")
    else:
        print(f"PO {po_no} not found.")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python ariba_p21_agent.py <cxml_file>")
        print("       python ariba_p21_agent.py --test")
        print("       python ariba_p21_agent.py --verify <po_no>")
        sys.exit(1)

    if sys.argv[1] == '--test':
        # Test with existing cXML sample
        sample = r'C:\Claude\Work\EnPro\Projects\Autola_AI\Ariba_Samples\4900781519.txt'
        print(f"Parsing cXML: {sample}")
        header, lines, raw = parse_cxml(sample)
        print(f"PO: {header['po_no']} | {len(lines)} lines | ${header['total_amt']:,.2f}")
        print(f"Ship To: {header.get('ship2_name', 'N/A')}, {header.get('ship2_city', '')}, {header.get('ship2_state', '')}")
        print(f"Buyer: {header.get('buyer', 'N/A')} ({header.get('buyer_email', '')})")
        for l in lines:
            print(f"  Line {l['line_no']}: {l.get('item_description', '')[:50]} | ${l.get('unit_price', 0):,.2f}")
        print("\nParsing successful. PO already in database (loaded via SQL).")
        verify_import('4900781519')

    elif sys.argv[1] == '--test-pdf':
        # Test with a Brittany PDF sample
        pdf_dir = r'C:\Claude\Work\EnPro\Projects\Autola_AI\Brittany_Samples'
        sample = sys.argv[2] if len(sys.argv) > 2 else os.path.join(pdf_dir, '442797.pdf')
        print(f"Parsing PDF via Azure Document Intelligence: {os.path.basename(sample)}")
        print("Sending to Azure...")
        header, lines, raw = parse_pdf(sample)
        print(f"\nPO: {header.get('po_no', 'N/A')} | {len(lines)} lines | ${header.get('total_amt', 0):,.2f}")
        print(f"Supplier: {header.get('supplier_name', 'N/A')}")
        print(f"Ship To: {header.get('ship2_name', 'N/A')}, {header.get('ship2_city', '')}, {header.get('ship2_state', '')}")
        print(f"Terms: {header.get('terms', 'N/A')}")
        for l in lines:
            print(f"  Line {l['line_no']}: {l.get('item_description', '')[:50]} | Qty: {l.get('qty_ordered', 0)} | ${l.get('unit_price', 0):,.2f}")

        if input("\nImport to P21 sandbox? (y/n): ").lower() == 'y':
            result = import_to_p21(header, lines, raw)
            print(f"\nResult: {result['status']}")
            if result['status'] == 'IMPORTED':
                verify_import(result['po_no'])
            elif result['status'] == 'DUPLICATE':
                print(f"PO {result['po_no']} already exists.")
                verify_import(result['po_no'])

    elif sys.argv[1] == '--verify':
        po_no = sys.argv[2] if len(sys.argv) > 2 else '4900781519'
        verify_import(po_no)

    else:
        # Import from file — auto-detect type
        file_path = sys.argv[1]
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            sys.exit(1)

        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            print(f"Detected PDF: {os.path.basename(file_path)}")
            print("Sending to Azure Document Intelligence...")
            header, lines, raw = parse_pdf(file_path)
            source = 'PDF'
        elif ext in ('.xml', '.txt', '.cxml'):
            print(f"Detected cXML: {os.path.basename(file_path)}")
            header, lines, raw = parse_cxml(file_path)
            source = 'CXML'
        else:
            print(f"Unknown file type: {ext}. Trying cXML parser...")
            header, lines, raw = parse_cxml(file_path)
            source = 'CXML'

        print(f"\nParsed ({source}): PO {header.get('po_no', 'N/A')} | {len(lines)} lines | ${header.get('total_amt', 0):,.2f}")
        print(f"Supplier: {header.get('supplier_name', 'N/A')}")
        print(f"Ship To: {header.get('ship2_name', 'N/A')}")
        for l in lines:
            print(f"  Line {l['line_no']}: {l.get('item_description', '')[:50]} | ${l.get('unit_price', 0):,.2f}")

        print("\nImporting to P21 sandbox...")
        result = import_to_p21(header, lines, raw)
        print(f"Result: {result['status']}")

        if result['status'] == 'IMPORTED':
            print(f"\nImported PO {result['po_no']}")
            print(f"  Supplier: {result['supplier']}")
            print(f"  Ship To:  {result['ship_to']}")
            print(f"  Total:    ${result['total']:,.2f}")
            print(f"  Lines:    {result['lines']}")
            print(f"  Buyer:    {result['buyer']}")
            verify_import(result['po_no'])
        elif result['status'] == 'DUPLICATE':
            print(f"PO {result['po_no']} already exists. Skipping.")
            verify_import(result['po_no'])
