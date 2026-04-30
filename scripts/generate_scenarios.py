import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

output_dir = "test_system"
os.makedirs(output_dir, exist_ok=True)

try:
    font_title = ImageFont.truetype("arialbd.ttf", 40)
    font_header = ImageFont.truetype("arialbd.ttf", 20)
    font_normal = ImageFont.truetype("arial.ttf", 18)
    font_bold = ImageFont.truetype("arialbd.ttf", 18)
except IOError:
    font_title = ImageFont.load_default()
    font_header = ImageFont.load_default()
    font_normal = ImageFont.load_default()
    font_bold = ImageFont.load_default()

def create_invoice(filename, vendor, amount, is_blurry=False, shady=False):
    width, height = 800, 1050
    img = Image.new('RGB', (width, height), color=(255, 255, 255))
    d = ImageDraw.Draw(img)

    if shady:
        d.text((50, 50), "INVOICE FOR SERVICES", fill=(0, 0, 0), font=font_title)
        d.text((50, 150), f"From: {vendor}", fill=(0, 0, 0), font=font_normal)
        d.text((50, 200), f"Amount Due: USD {amount:,.2f}", fill=(0, 0, 0), font=font_normal)
        d.text((50, 300), "Please pay immediately to offshore account.", fill=(0, 0, 0), font=font_normal)
    else:
        primary_color = (44, 62, 80)
        d.rectangle([0, 0, width, 120], fill=primary_color)
        d.text((50, 40), "INVOICE", fill=(255, 255, 255), font=font_title)
        d.text((width - 350, 40), vendor, fill=(255, 255, 255), font=font_header)
        d.text((50, 200), f"Total Due: USD {amount:,.2f}", fill=(0, 0, 0), font=font_title)

    if is_blurry:
        img = img.filter(ImageFilter.GaussianBlur(3))

    img.save(f"{output_dir}/{filename}")

# Scenario 2: Budget Breach (massive amount)
create_invoice("high_amount_invoice.png", "Google Ads", 500000.00)

# Scenario 3: Blurry/OCR Challenge
create_invoice("blurry_invoice.png", "Office Supplies Co", 450.00, is_blurry=True)

# Scenario 4: Shady Vendor (High Risk)
create_invoice("shady_vendor_invoice.png", "XYZ Shell Corp", 45000.00, shady=True)

print("Generated scenario invoices.")
