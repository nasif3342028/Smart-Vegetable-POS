import os
from datetime import datetime
from fpdf import FPDF
from app_paths import BASE_DIR


RECEIPTS_DIR = os.path.join(BASE_DIR, "receipts")


class ReceiptGenerator:

    def __init__(self, output_dir=RECEIPTS_DIR):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            print(f"[RECEIPT] Created receipts folder: {self.output_dir}")

    def generate(self, customer_info, cart_items, session_id):
        if not cart_items:
            print("[RECEIPT] No items to generate receipt for.")
            return None

        grand_total = sum(item["total"] for item in cart_items)
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%I:%M:%S %p")

        safe_name = customer_info["name"].replace(" ", "_")
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        filename = f"receipt_{safe_name}_{timestamp_str}.pdf"
        filepath = os.path.join(self.output_dir, filename)

        print(f"[RECEIPT] Generating receipt: {filename}")

        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        page_width = pdf.w - 2 * pdf.l_margin

        pdf.set_font("Helvetica", "B", 20)
        pdf.cell(page_width, 12, "SMART VEGETABLE POS", ln=True, align="C")

        pdf.set_font("Helvetica", "", 11)
        pdf.cell(page_width, 7, "Automated Weighing and Billing System", ln=True, align="C")

        pdf.ln(3)
        pdf.set_draw_color(0, 180, 150)
        pdf.set_line_width(0.8)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_width, pdf.get_y())
        pdf.ln(5)

        pdf.set_font("Helvetica", "", 10)
        pdf.cell(page_width / 2, 6, f"Receipt No: {session_id}", ln=False)
        pdf.cell(page_width / 2, 6, f"Date: {date_str}", ln=True, align="R")

        pdf.cell(page_width / 2, 6, f"Customer: {customer_info['name']}", ln=False)
        pdf.cell(page_width / 2, 6, f"Time: {time_str}", ln=True, align="R")

        pdf.cell(page_width / 2, 6, f"Mobile: {customer_info['mobile']}", ln=True)

        pdf.ln(3)
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.3)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_width, pdf.get_y())
        pdf.ln(5)

        col_no = 15
        col_item = 45
        col_weight = 35
        col_rate = 35
        col_total = page_width - col_no - col_item - col_weight - col_rate

        pdf.set_fill_color(0, 120, 100)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 10)

        pdf.cell(col_no, 8, "#", border=1, align="C", fill=True)
        pdf.cell(col_item, 8, "Item", border=1, align="C", fill=True)
        pdf.cell(col_weight, 8, "Weight (kg)", border=1, align="C", fill=True)
        pdf.cell(col_rate, 8, "Rate/kg", border=1, align="C", fill=True)
        pdf.cell(col_total, 8, "Total (BDT)", border=1, align="C", fill=True)
        pdf.ln()

        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 10)

        for i, item in enumerate(cart_items):
            if i % 2 == 0:
                pdf.set_fill_color(245, 245, 245)
            else:
                pdf.set_fill_color(255, 255, 255)

            pdf.cell(col_no, 8, str(i + 1), border=1, align="C", fill=True)
            pdf.cell(col_item, 8, item["vegetable"].upper(), border=1, align="L", fill=True)
            pdf.cell(col_weight, 8, f"{item['weight_kg']:.3f}", border=1, align="C", fill=True)
            pdf.cell(col_rate, 8, f"{item['price_per_kg']:.2f}", border=1, align="C", fill=True)
            pdf.cell(col_total, 8, f"{item['total']:.2f}", border=1, align="R", fill=True)
            pdf.ln()

        pdf.set_font("Helvetica", "B", 11)
        pdf.set_fill_color(0, 120, 100)
        pdf.set_text_color(255, 255, 255)

        total_label_width = col_no + col_item + col_weight + col_rate
        pdf.cell(total_label_width, 10, "GRAND TOTAL", border=1, align="R", fill=True)
        pdf.cell(col_total, 10, f"{grand_total:.2f} BDT", border=1, align="R", fill=True)
        pdf.ln()

        pdf.set_text_color(0, 0, 0)
        pdf.ln(10)

        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(page_width, 6, f"Items purchased: {len(cart_items)}", ln=True, align="C")

        pdf.ln(5)
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.3)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_width, pdf.get_y())
        pdf.ln(5)

        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(page_width, 6, "Thank you for your purchase!", ln=True, align="C")
        pdf.cell(page_width, 6, "Smart Vegetable POS - Automated Weighing System", ln=True, align="C")

        pdf.output(filepath)
        print(f"[RECEIPT] Receipt saved: {filepath}")

        return filepath