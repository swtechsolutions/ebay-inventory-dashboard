# Inventory Management & eBay HTML Generator

A modern, responsive web application built with Python and Flask to manage inventory, track sales performance, calculate net profits, and instantly generate formatted HTML descriptions for eBay listings.

---

## Purpose & Developer Assistant Goals

This project is developed with a clear focus on clean software design, continuous learning, and actionable code documentation.

### Core Goals
- **Code Creation:** Writing complete, production-ready code to achieve application features and UI enhancements.
- **Education:** Documenting code mechanics and concepts (e.g., ORM models, Jinja2 templating, SQLite initialization) to build a deep understanding of full-stack Flask development.
- **Clear Instructions:** Providing easy-to-follow, step-by-step guides for setup, deployment, and template customization.
- **Thorough Documentation:** Maintaining detailed code comments, clear folder structures, and usage workflows.

> **Note:** Development discussions and contributions for this repository are strictly focused on software engineering, web development, and coding topics.

---

## Key Features

- **Inventory Dashboard**: View, sort, and track all your products at a glance with clean visual cards.
- **Auto-Generated SKUs**: Automatically generates sequential SKUs (e.g., `SW10001`) if left blank upon item creation.
- **Product Gallery & Lightbox**: Upload multiple images per item with click-to-expand lightbox viewing and direct download capabilities.
- **Financial Performance Tracking**: Automatically calculates gross revenue, total expense breakdowns, and net profit once an item's status is updated to **Sold**.
- **eBay HTML Description Generator**: Automatically converts product details and formatted descriptions into standard HTML ready to copy and paste directly into eBay's description editor.
- **Custom Branding & Structured Layouts**: Features modern CSS card designs and automated footer branding linking to Southwest Tech Solutions.

---

## Tech Stack & Libraries

- **Backend**: [Python 3.x](https://www.python.org/), [Flask](https://flask.palletsprojects.com/)
- **Database & ORM**: [SQLite](https://www.sqlite.org/), [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)
- **File & Form Handling**: [Werkzeug](https://werkzeug.palletsprojects.com/) (`secure_filename`)
- **Frontend**: HTML5, CSS3 (CSS Grid/Flexbox), JavaScript (Vanilla JS for Lightbox & Clipboard API)
- **Templating**: Jinja2

---

## Project Directory Structure

```text
inventory-app/
│
├── app.py                   # Main Flask application logic, models, and routes
├── .gitignore               # Configured to ignore SQLite DB, venv, and uploaded media
├── README.md                # Project documentation and developer instructions
│
├── static/
│   └── uploads/             # User-uploaded product image files
│       └── .gitkeep         # Preserves empty upload directory in Git
│
└── templates/
    ├── base.html            # Base template with global header, styling, and footer
    ├── index.html           # Main inventory list dashboard
    ├── view_item.html       # Detailed item view cards, financial stats, and eBay HTML
    └── edit_item.html       # Add / Edit item form with multi-image upload
```

---

## Installation Instructions

Clone the repo
```
git clone https://github.com/swtechsolutions/ebay-inventory-dashboard.git
```

Create a venv and activate it
```python
cd ebay-inventory-dashboard
python3 -m venv .venv
source .venv/bin/activate
```

Install requirements
```python
pip install -r requirements.txt
```

Run the app
```python
python3 app.py
```

Open the website
```
http://127.0.0.1:5000
```