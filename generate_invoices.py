import os
import random
from datetime import datetime, timedelta
from faker import Faker
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from config import get_supabase

fake = Faker()
sb = get_supabase()

output_dir = "test_system"
os.makedirs(output_dir, exist_ok=True)

try:
    font_title = ImageFont.truetype("arialbd.ttf", 40)
    font_header = ImageFont.truetype("arialbd.ttf", 20)
    font_normal = ImageFont.truetype("arial.ttf", 18)
    font_small = ImageFont.truetype("arial.ttf", 14)
    font_bold = ImageFont.truetype("arialbd.ttf", 18)
except IOError:
    font_title = ImageFont.load_default()
    font_header = ImageFont.load_default()
    font_normal = ImageFont.load_default()
    font_small = ImageFont.load_default()
    font_bold = ImageFont.load_default()

def draw_professional_invoice(i, vendor_name, scenario="safe"):
    vendor_address = fake.address().replace('\n', ', ')
    client_name = "Semmmrr Financial"
    client_address = fake.address().replace('\n', ', ')
    invoice_number = f"INV-{fake.random_int(min=10000, max=99999)}"
    
    invoice_date = fake.date_this_year().strftime("%Y-%m-%d")
    due_date = (datetime.strptime(invoice_date, "%Y-%m-%d") + timedelta(days=30)).strftime("%Y-%m-%d")
    
    currency = "USD"
    
    items = []
    total_amount = 0
    
    # Adjust amounts based on scenario
    if scenario == "budget_breach":
        num_items = random.randint(1, 3)
        price_range = (50000.0, 150000.0)
    elif scenario == "shady":
        num_items = 1
        price_range = (20000.0, 45000.0)
    else:
        num_items = random.randint(2, 5)
        price_range = (50.0, 1000.0)

    for _ in range(num_items):
        desc = fake.catch_phrase() if scenario != "shady" else "Consulting Fees"
        qty = random.randint(1, 10) if scenario == "safe" or scenario == "blurry" else 1
        price = round(random.uniform(*price_range), 2)
        amount = qty * price
        total_amount += amount
        items.append((desc[:30], qty, price, amount))
        
    tax = round(total_amount * 0.1, 2)
    grand_total = total_amount + tax

    width, height = 800, 1050
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    d = ImageDraw.Draw(img)

    primary_color = (44, 62, 80)
    secondary_color = (236, 240, 241)
    text_color = (51, 51, 51)
    
    d.rectangle([0, 0, width, 120], fill=primary_color)
    d.text((50, 40), "INVOICE", fill=(255, 255, 255), font=font_title)
    
    d.text((width - 350, 40), vendor_name, fill=(255, 255, 255), font=font_header)
    d.text((width - 350, 70), vendor_address[:45], fill=(200, 200, 200), font=font_small)

    d.text((50, 160), "Billed To:", fill=primary_color, font=font_bold)
    d.text((50, 190), client_name, fill=text_color, font=font_normal)
    d.text((50, 215), client_address[:45], fill=text_color, font=font_small)

    d.text((width - 350, 160), f"Invoice Number: {invoice_number}", fill=text_color, font=font_bold)
    d.text((width - 350, 190), f"Date of Issue: {invoice_date}", fill=text_color, font=font_normal)
    d.text((width - 350, 215), f"Due Date: {due_date}", fill=text_color, font=font_normal)

    y_offset = 300
    d.rectangle([50, y_offset, width - 50, y_offset + 40], fill=primary_color)
    d.text((60, y_offset + 10), "Description", fill=(255, 255, 255), font=font_bold)
    d.text((450, y_offset + 10), "Qty", fill=(255, 255, 255), font=font_bold)
    d.text((550, y_offset + 10), "Unit Price", fill=(255, 255, 255), font=font_bold)
    d.text((680, y_offset + 10), "Amount", fill=(255, 255, 255), font=font_bold)

    y_offset += 50
    for idx, (desc, qty, price, amount) in enumerate(items):
        if idx % 2 == 0:
            d.rectangle([50, y_offset - 10, width - 50, y_offset + 30], fill=secondary_color)
        d.text((60, y_offset), desc, fill=text_color, font=font_normal)
        d.text((450, y_offset), str(qty), fill=text_color, font=font_normal)
        d.text((550, y_offset), f"{price:,.2f}", fill=text_color, font=font_normal)
        d.text((680, y_offset), f"{amount:,.2f}", fill=text_color, font=font_normal)
        y_offset += 40

    y_offset += 40
    d.line([(450, y_offset), (width - 50, y_offset)], fill=primary_color, width=2)
    y_offset += 20
    d.text((450, y_offset), "Subtotal:", fill=text_color, font=font_bold)
    d.text((680, y_offset), f"{total_amount:,.2f}", fill=text_color, font=font_normal)
    
    y_offset += 30
    d.text((450, y_offset), "Tax (10%):", fill=text_color, font=font_bold)
    d.text((680, y_offset), f"{tax:,.2f}", fill=text_color, font=font_normal)

    y_offset += 30
    d.rectangle([430, y_offset - 10, width - 50, y_offset + 40], fill=primary_color)
    d.text((450, y_offset), "Total Due:", fill=(255, 255, 255), font=font_header)
    d.text((630, y_offset), f"{currency} {grand_total:,.2f}", fill=(255, 255, 255), font=font_header)

    d.text((50, height - 80), "Thank you for your business!", fill=primary_color, font=font_bold)
    d.text((50, height - 50), "Please make checks payable to " + vendor_name, fill=text_color, font=font_small)

    if scenario == "blurry":
        img = img.filter(ImageFilter.GaussianBlur(3))

    filename = f"{output_dir}/{scenario}_invoice_{i:02d}.png"
    img.save(filename)

# Get vendors from DB
res = sb.table('vendors').select('name').execute()
real_vendors = [v['name'] for v in res.data] if res.data else ["Acme Corp"]

# Generate 20 Safe Invoices
for i in range(1, 21):
    vendor = random.choice(real_vendors)
    draw_professional_invoice(i, vendor, scenario="safe")

# Generate 5 Budget Breach Invoices
for i in range(1, 6):
    vendor = random.choice(real_vendors)
    draw_professional_invoice(i, vendor, scenario="budget_breach")

# Generate 5 Blurry Invoices
for i in range(1, 6):
    vendor = random.choice(real_vendors)
    draw_professional_invoice(i, vendor, scenario="blurry")

# Generate 5 Shady Vendor Invoices
for i in range(1, 6):
    # Intentional shady vendors not in the DB, or suspicious sounding
    vendor = random.choice(["Offshore Holdings LLC", "XYZ Shell Corp", "Unknown Entity Inc", "Ghost Services Partners"])
    draw_professional_invoice(i, vendor, scenario="shady")

print("Successfully generated 35 professional invoices covering all scenarios.")
