# Inventory Management & eBay HTML Generator

A web application built with Python and Flask to manage resale inventory, track sales and profit, run reports, and generate formatted HTML descriptions for eBay listings.

---

## Key Features

- **Inventory List**: Search by title or SKU, filter by category, and page through all your items with thumbnail, status, listing price and profit at a glance.
- **eBay Categories**: Items use eBay Canada's own categories (35 top-level, 475 sub-categories) with a searchable picker, and each item page shows the eBay category ID to use when listing.
- **Item Tracking**: Record SKU, title, eBay category, condition, description and status (Unlisted, Listed, Sold). Date added, date listed and date sold are recorded automatically, and the sold date can be changed by hand.
- **Package Size & Weight**: Record the packed box's length, width and height (cm) and weight (kg + g, as on eBay's shipping form). Existing databases get the new fields automatically when the app starts.
- **Multiple Photos per Item**: Upload several photos per item, add more later, and delete individual photos from the edit page.
- **Profit Tracking**: Enter revenue (item price, shipping paid, tax collected) and expenses (transaction, promo and other fees, item cost, shipping cost, tax paid); total revenue, total costs, profit and margin are calculated for you.
- **eBay HTML Description Generator**: Each item page produces ready-to-paste HTML for eBay's description editor, with a one-click copy button.
- **Reports**: Sold and unsold item reports with charts and tables, filterable by date range and category (top level or sub-category), and grouped by either level:
  - Sold: profit, revenue, expenses, margin, average days to sell, monthly revenue/expenses/profit chart, profit by category, expense breakdown, and full item detail.
  - Unsold: money invested, listing value, potential profit, cost vs. listing value by category, and inventory age.
  - Export any report to CSV (opens in Excel).

---

## Tech Stack & Libraries

- **Backend**: [Python 3.9+](https://www.python.org/), [Flask](https://flask.palletsprojects.com/)
- **Database & ORM**: [SQLite](https://www.sqlite.org/), [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)
- **Frontend**: HTML, CSS, vanilla JavaScript, [Chart.js](https://www.chartjs.org/) 4.4.1 (bundled locally in `static/vendor/`, so no internet connection is needed)
- **Templating**: Jinja2

---

## Project Directory Structure

```text
ebay-inventory-dashboard/
│
├── app.py                   # Flask application: models, routes and reports
├── ebay_categories.py       # Loads the eBay category list
├── requirements.txt         # Python packages to install
├── ebay-app.service         # Sample systemd service file (edit paths before use)
├── .gitignore               # Ignores the database, virtual environment and uploaded photos
├── README.md
├── LICENSE                  # MIT License
│
├── data/
│   └── ebay_categories_ca.txt  # eBay Canada categories and IDs (from ebay.ca/n/all-categories)
│
├── instance/
│   └── inventory.db         # SQLite database (created automatically on first run)
│
├── static/
│   ├── uploads/             # Uploaded product photos
│   ├── js/
│   │   └── category-picker.js  # Search box for the category dropdown
│   └── vendor/
│       └── chart.umd.min.js # Chart.js library used by the reports page
│
└── templates/
    ├── base.html            # Shared layout and navigation bar
    ├── _category.html       # Category picker and category filter components
    ├── _package.html        # Package size & weight form fields
    ├── index.html           # Inventory list
    ├── add_item.html        # Add item form
    ├── edit_item.html       # Edit item form and photo management
    ├── view_item.html       # Item details, financials and eBay HTML
    └── reports.html         # Sales and inventory reports
```

---

## Installation Instructions

### Prerequisites

- **Python 3.9 or newer**. Check your version with `python3 --version` (on Windows: `python --version`).
- **Git**, to clone the repository.
- On Debian/Ubuntu, the venv module may need installing first: `sudo apt install python3-venv`

### 1. Clone the repo

```bash
git clone https://github.com/swtechsolutions/ebay-inventory-dashboard.git
cd ebay-inventory-dashboard
```

### 2. Create a virtual environment and activate it

Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Your prompt should now start with `(.venv)`. Activate the virtual environment again each time you open a new terminal to run the app.

### 3. Install requirements

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
python3 app.py
```

On Windows use `python app.py`. The first run creates the database at `instance/inventory.db`; the `static/uploads/` folder for photos is created automatically if missing.

### 5. Open the website

```
http://127.0.0.1:5000
```

Press `Ctrl+C` in the terminal to stop the app.

> **Note:** The app currently listens only on `127.0.0.1`, so it can be opened only from the computer it is running on. It also runs in Flask's debug mode, which is meant for local use. Do not expose it to the internet.

---

## Sample Data

To try out the app or test changes, add 30 sample items (sold, listed and unlisted, across many eBay categories):

```bash
python3 seed_sample_data.py            # add the sample items
python3 seed_sample_data.py --reset    # remove and re-add them (dates recalculated from today)
python3 seed_sample_data.py --remove   # remove all sample items
```

Sample items have SKUs starting with `DEMO-`; the script never changes any other items.

---

## Updating to the Latest Version

From the project folder, with the virtual environment activated:

```bash
git pull
pip install -r requirements.txt
```

Then restart the app.

---

## Your Data & Backups

Your data is **not** stored in Git (see `.gitignore`). To back up or move your inventory to another computer, copy these two locations:

- `instance/inventory.db` – all items, prices and dates
- `static/uploads/` – all product photos

Stop the app before copying the database so the copy is complete.

---

## Updating the eBay Category List

eBay occasionally adds, renames or removes categories. The list lives in `data/ebay_categories_ca.txt`, one category per line:

```text
TOP|Computers/Tablets & Networking|58058
SUB|Laptops & Netbooks|175672
```

Each `TOP` line is a top-level category and the `SUB` lines under it are its sub-categories, with the eBay category ID last. Compare against https://www.ebay.ca/n/all-categories, edit the file, and restart the app. Items store the full category path (e.g. `Computers/Tablets & Networking > Laptops & Netbooks`), so if a category is renamed, existing items keep the old name and show it as an "old category" until you pick a new one.

---

## License

This project is released under the [MIT License](LICENSE).

Third-party components included in this repository keep their own licenses:

- **Chart.js** 4.4.1 (`static/vendor/chart.umd.min.js`) – MIT License, © Chart.js Contributors. The license notice is kept at the top of the file.

The eBay category names and IDs in `data/ebay_categories_ca.txt` come from eBay (https://www.ebay.ca/n/all-categories) and are not covered by this project's license. eBay is a trademark of eBay Inc.; this project is not affiliated with or endorsed by eBay.
