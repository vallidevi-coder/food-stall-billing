# NextGen Food Stall Billing & QR Ordering System

This ready-to-run school event project uses the supplied item/price list.

## Included features
- Customer QR ordering page
- Automatic token number
- Automatic stock deduction
- Automatic subtotal, discount and total
- Approximate waiting time based on live queue
- Billing/packing station receives orders automatically
- Cash / UPI payment status
- Packing status: Received → Packing → Ready → Collected
- Large token display screen for ready orders
- Admin controls to change stock, prices, discount and average minutes/order during the event
- Customer order tracking page
- SQLite database; no separate database server required

## Items loaded from your Excel file
- Vanilla Cupcake — ₹60
- Red Velvet Cupcake — ₹60
- Lemon Cupcake — ₹60
- Chocolate Cupcake — ₹65
- Chocolate Overload Cookie — ₹60
- Choc Chip Cookie — ₹50
- Veg Sandwich — ₹60
- Cheese Sandwich — ₹70
- Chips Chaat — ₹50
- Pav Bhaji — ₹80
- Classic Sweet Lemonade — ₹40
- Sweet & Sour Lemonade — ₹40
- Strawberry Crush Lemonade — ₹45
- Egg Brownie — ₹60
- Eggless Brownie — ₹60

## Windows setup
1. Install Python 3.11+.
2. Double-click `START_FOOD_STALL.bat`.
3. The first run installs the required packages.
4. Open the displayed address.
5. On the event Wi-Fi, phones can use the computer's LAN IP, for example `http://192.168.1.10:5000/`.
6. Open `/admin` for controls, `/packing` for the billing/packing computer, and `/display` for a TV/projector.
7. Open `/qr` and print/save the QR code. Customers scan it to reach the order page.

## Important network note
All devices must be on the same Wi-Fi/LAN, and Windows Firewall must allow Python/port 5000 on the Private network.

## Optional: create a real Windows EXE
Run `BUILD_EXE.bat`. It creates a `dist` folder with a Windows executable using PyInstaller. Build it on a Windows computer.

## Event workflow
1. Customer scans QR.
2. Customer selects food and submits.
3. System creates token and reduces stock.
4. Billing/packing computer sees the new order.
5. Staff starts packing.
6. Payment is marked Cash or UPI.
7. Staff marks order Ready.
8. Token appears on the display and customer tracking page.
9. Customer hears/reads the token and collects after payment.
10. Admin can change stock, price, discount and preparation time at any point.
