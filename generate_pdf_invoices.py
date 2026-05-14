import os
import random
from datetime import datetime, timedelta
from faker import Faker
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

fake = Faker()

OUTPUT_DIR = "test_invoices"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Vendors from erp_seed.py
EXISTING_VENDORS = [
    "AWS Cloud Services", "Google Cloud Platform", "Microsoft Azure",
    "GitHub Enterprise", "Slack", "Atlassian", "DataDog",
    "Salesforce", "HubSpot", "LinkedIn Marketing", "Facebook Ads",
    "Google Ads", "Office Supplies Co", "WeWork", "Legal Counsel LLP",
    "Deloitte Audit", "Recruiting Partners Inc", "Coursera Business",
    "Lab Equipment Supplier", "Research Materials Co"
]

NEW_VENDORS = [
    "Global Tech Solutions", "Peak Performance Inc", "Nexus Strategy Group",
    "Silverline Logistics", "Quantum Cyber Security"
]

def generate_pdf(filename, vendor_name, amount, inv_number, items):
    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor("#2c3e50"), spaceAfter=20)
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor("#7f8c8d"), leading=12)
    label_style = ParagraphStyle('LabelStyle', parent=styles['Normal'], fontSize=10, fontWeight='Bold', textColor=colors.HexColor("#2c3e50"))
    
    elements = []
    
    # Header: Company Name and Invoice Label
    header_data = [
        [Paragraph(vendor_name, title_style), Paragraph("INVOICE", ParagraphStyle('InvLabel', parent=title_style, alignment=2, fontSize=30, textColor=colors.HexColor("#ecf0f1")))]
    ]
    header_table = Table(header_data, colWidths=[120*mm, 70*mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BACKGROUND', (1,0), (1,0), colors.HexColor("#2c3e50")),
        ('LEFTPADDING', (1,0), (1,0), 10),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 10*mm))
    
    # Vendor & Client Info
    info_data = [
        [Paragraph("FROM:", label_style), Paragraph("BILLED TO:", label_style)],
        [Paragraph(f"{vendor_name}<br/>{fake.street_address()}<br/>{fake.city()}, {fake.state()}<br/>{fake.postcode()}<br/>{fake.email()}", header_style),
         Paragraph("Semmmrr Financial Corp<br/>88 Enterprise Way<br/>Financial District<br/>Istanbul, Turkey<br/>finance@semmmrr.test", header_style)]
    ]
    info_table = Table(info_data, colWidths=[95*mm, 95*mm])
    elements.append(info_table)
    elements.append(Spacer(1, 10*mm))
    
    # Invoice Metadata (Number, Date)
    meta_data = [
        [Paragraph("Invoice Number:", label_style), Paragraph(inv_number, header_style)],
        [Paragraph("Invoice Date:", label_style), Paragraph(datetime.now().strftime("%Y-%m-%d"), header_style)],
        [Paragraph("Due Date:", label_style), Paragraph((datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d"), header_style)]
    ]
    meta_table = Table(meta_data, colWidths=[40*mm, 150*mm])
    elements.append(meta_table)
    elements.append(Spacer(1, 10*mm))
    
    # Line Items Table
    table_data = [["Description", "Qty", "Unit Price", "Total"]]
    for item, qty, price in items:
        table_data.append([item, str(qty), f"${price:,.2f}", f"${(qty * price):,.2f}"])
    
    # Totals
    subtotal = sum(q * p for _, q, p in items)
    tax = subtotal * 0.1
    total = subtotal + tax
    
    table_data.append(["", "", "Subtotal:", f"${subtotal:,.2f}"])
    table_data.append(["", "", "Tax (10%):", f"${tax:,.2f}"])
    table_data.append(["", "", "TOTAL DUE:", f"${total:,.2f}"])
    
    items_table = Table(table_data, colWidths=[90*mm, 20*mm, 40*mm, 40*mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2c3e50")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-4), colors.HexColor("#f8f9f9")),
        ('GRID', (0,0), (-1,-4), 1, colors.HexColor("#dee2e6")),
        ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
        ('FONTNAME', (-2,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (-2,-1), (-1,-1), 14),
        ('TOPPADDING', (0,-3), (-1,-1), 10),
    ]))
    elements.append(items_table)
    
    elements.append(Spacer(1, 20*mm))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dee2e6")))
    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("Notes: Please quote invoice number on all payments. Thank you for your business!", header_style))
    
    doc.build(elements)

def create_scenarios():
    scenarios = [
        # 1. Auto-Approval (Existing Vendor, <10k)
        {
            "name": "01_auto_approve_aws.pdf",
            "vendor": "AWS Cloud Services",
            "items": [("Monthly Cloud Hosting - EC2", 1, 4200.50), ("S3 Storage Fees", 1, 800.00)]
        },
        # 2. Manager Approval (Existing Vendor, 10k-100k)
        {
            "name": "02_manager_salesforce.pdf",
            "vendor": "Salesforce",
            "items": [("Enterprise License Renewal (50 users)", 1, 24500.00), ("Premium Support Tier", 1, 5000.00)]
        },
        # 3. Senior Manager Approval (Existing Vendor, >100k)
        {
            "name": "03_senior_google_cloud.pdf",
            "vendor": "Google Cloud Platform",
            "items": [("Compute Engine - Production Cluster", 1, 145000.00), ("Cloud SQL Database Hosting", 1, 14466.59), ("Tax (Estimated)", 1, 0)] # Total will be >100k
        },
        # 4. New Vendor (Flagged by Validation, <10k)
        {
            "name": "04_new_vendor_global_tech.pdf",
            "vendor": "Global Tech Solutions",
            "items": [("IT Consultancy - Initial Setup", 1, 8500.00)]
        },
        # 5. Duplicate (Same as #4 but different number - actually duplicate needs same number)
        {
            "name": "05_duplicate_global_tech.pdf",
            "vendor": "Global Tech Solutions",
            "items": [("IT Consultancy - Initial Setup", 1, 8500.00)],
            "inv_number": "INV-GTS-001"
        },
        # 6. Another auto-approve
        {
            "name": "06_auto_approve_github.pdf",
            "vendor": "GitHub Enterprise",
            "items": [("Organization Seats (100)", 1, 2100.00)]
        },
        # 7. Low Amount, High Budget Utilisation (Manager)
        {
            "name": "07_budget_alert_slack.pdf",
            "vendor": "Slack",
            "items": [("Annual Subscription - Pro", 1, 9500.00)]
        },
        # 8. High Amount, New Vendor (Senior Manager)
        {
            "name": "08_senior_new_nexus.pdf",
            "vendor": "Nexus Strategy Group",
            "items": [("Global Expansion Consultancy", 1, 150000.00)]
        },
        # 9-15. Various Auto-approvals
        {
            "name": "09_auto_atlassian.pdf",
            "vendor": "Atlassian",
            "items": [("Jira Software Premium", 1, 1200.00), ("Confluence Standard", 1, 400.00)]
        },
        {
            "name": "10_auto_datadog.pdf",
            "vendor": "DataDog",
            "items": [("Infrastructure Monitoring", 1, 3500.00), ("APM Trace Collection", 1, 1500.00)]
        },
        {
            "name": "11_auto_hubspot.pdf",
            "vendor": "HubSpot",
            "items": [("Marketing Hub Enterprise", 1, 4500.00)]
        },
        {
            "name": "12_auto_we_work.pdf",
            "vendor": "WeWork",
            "items": [("Private Office - Month to Month", 1, 6500.00)]
        },
        {
            "name": "13_auto_office_supplies.pdf",
            "vendor": "Office Supplies Co",
            "items": [("Assorted Stationery", 1, 450.00), ("Ergonomic Chairs (2)", 2, 800.00)]
        },
        {
            "name": "14_auto_linkedin.pdf",
            "vendor": "LinkedIn Marketing",
            "items": [("Q2 Recruitment Campaign", 1, 7500.00)]
        },
        {
            "name": "15_auto_facebook_ads.pdf",
            "vendor": "Facebook Ads",
            "items": [("Weekly Ad Spend - May Week 2", 1, 5400.00)]
        },
        {
            "name": "16_perfect_storm.pdf",
            "vendor": "Global Synergy Dynamics (PERFECT STORM)",
            "items": [("Complex Consultancy & Implementation", 1, 250000.00)]
        }
    ]
    
    # Overriding number for duplicate test
    scenarios[3]["inv_number"] = "INV-GTS-001" 
    
    for s in scenarios:
        path = os.path.join(OUTPUT_DIR, s["name"])
        inv_num = s.get("inv_number", f"INV-{fake.random_int(1000, 9999)}")
        # Calculate total for logging but generate_pdf does it too
        sub = sum(q * p for _, q, p in s["items"])
        print(f"Generating {s['name']} for {s['vendor']} (Approx Total: ${sub*1.1:,.2f})")
        generate_pdf(path, s["vendor"], sub*1.1, inv_num, s["items"])

if __name__ == "__main__":
    create_scenarios()
    print("\nSuccessfully generated 6 professional PDF invoices in 'test_invoices/'")
