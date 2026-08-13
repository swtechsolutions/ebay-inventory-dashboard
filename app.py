import os
import sqlite3
import time
import re
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

# -------------------------------------------------------------
# CONFIGURATION & CONSTANTS
# -------------------------------------------------------------
# Base upload directory inside project root
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DB_NAME = "inventory_v3.db"

# -------------------------------------------------------------
# DATABASE HELPER & INITIALIZATION
# -------------------------------------------------------------
def get_db():
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Enables column access by key name
    return conn

def generate_next_sku(cursor):
    """
    Calculates the next SWXXXXX SKU starting at SW20000.
    Finds the highest existing SKU matching 'SW%' and increments its integer component.
    """
    cursor.execute("SELECT sku FROM inventory WHERE sku LIKE 'SW%' ORDER BY sku DESC LIMIT 1")
    row = cursor.fetchone()
    
    if not row or not row['sku']:
        return "SW20000"
    
    # Extract numeric portion from SKU string (e.g., 'SW20000' -> 20000)
    match = re.search(r'SW(\d+)', row['sku'])
    if match:
        next_num = int(match.group(1)) + 1
        return f"SW{next_num}"
    
    return "SW20000"

def init_db():
    """
    Initializes SQLite tables and handles schema migrations safely.
    Applies unique constraints via indexing to avoid SQLite ALTER TABLE errors.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Main Inventory Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sku TEXT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            condition TEXT,
            freq_range TEXT,
            power_output TEXT,
            included_acc TEXT,
            tech_notes TEXT,
            purchase_price REAL DEFAULT 0.0,
            listing_price REAL DEFAULT 0.0,
            shipping_cost REAL DEFAULT 0.0,
            status TEXT DEFAULT 'In Stock'
        )
    ''')
    
    # 2. Schema Migration: Safely add 'sku' column if missing from older DB versions
    cursor.execute("PRAGMA table_info(inventory)")
    columns = [column[1] for column in cursor.fetchall()]
    if 'sku' not in columns:
        cursor.execute("ALTER TABLE inventory ADD COLUMN sku TEXT")
    
    # 3. Backfill missing SKUs for pre-existing items
    cursor.execute("SELECT id FROM inventory WHERE sku IS NULL OR sku = '' ORDER BY id ASC")
    items_without_sku = cursor.fetchall()
    
    for item in items_without_sku:
        new_sku = generate_next_sku(cursor)
        cursor.execute("UPDATE inventory SET sku = ? WHERE id = ?", (new_sku, item['id']))
    
    # 4. Enforce unique SKU constraint safely via an index
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_inventory_sku ON inventory(sku)")
    
    # 5. Image Table for 1-to-Many photo relationship
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS item_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            image_path TEXT,
            FOREIGN KEY(item_id) REFERENCES inventory(id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

# -------------------------------------------------------------
# FRONTEND ROUTING & STATIC FILE SERVING
# -------------------------------------------------------------
@app.route('/')
def index():
    """Renders the main single-page dashboard interface."""
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serves uploaded product images directly to the browser."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# -------------------------------------------------------------
# RESTFUL API ENDPOINTS
# -------------------------------------------------------------

@app.route('/api/items', methods=['GET'])
def get_items():
    """Retrieves all inventory items ordered by newest first, including associated images."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM inventory ORDER BY id DESC')
    rows = cursor.fetchall()
    
    items = []
    for row in rows:
        item = dict(row)
        cursor.execute('SELECT id, image_path FROM item_images WHERE item_id = ?', (item['id'],))
        item['images'] = [dict(img) for img in cursor.fetchall()]
        items.append(item)
        
    conn.close()
    return jsonify(items)

@app.route('/api/items/<int:item_id>', methods=['GET'])
def get_single_item(item_id):
    """Fetches details for a specific item by ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM inventory WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return jsonify({'error': 'Item not found'}), 404
        
    item = dict(row)
    cursor.execute('SELECT id, image_path FROM item_images WHERE item_id = ?', (item_id,))
    item['images'] = [dict(img) for img in cursor.fetchall()]
    conn.close()
    
    return jsonify(item)

@app.route('/api/items', methods=['POST'])
def add_item():
    """Creates a new inventory record with an auto-incremented SKU and uploads images."""
    title = request.form.get('title')
    category = request.form.get('category', 'Ham Radio')
    condition = request.form.get('condition', 'Used')
    freq_range = request.form.get('freq_range', 'N/A')
    power_output = request.form.get('power_output', 'N/A')
    included_acc = request.form.get('included_acc', 'None')
    tech_notes = request.form.get('tech_notes', '')
    purchase_price = float(request.form.get('purchase_price') or 0.0)
    listing_price = float(request.form.get('listing_price') or 0.0)
    shipping_cost = float(request.form.get('shipping_cost') or 0.0)
    status = request.form.get('status', 'In Stock')

    conn = get_db()
    cursor = conn.cursor()
    
    # Auto-generate next available SKU
    sku = generate_next_sku(cursor)

    cursor.execute('''
        INSERT INTO inventory (
            sku, title, category, condition, freq_range, 
            power_output, included_acc, tech_notes, 
            purchase_price, listing_price, shipping_cost, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (sku, title, category, condition, freq_range, power_output, included_acc, tech_notes, purchase_price, listing_price, shipping_cost, status))
    
    item_id = cursor.lastrowid

    # Handle image file uploads
    files = request.files.getlist('images')
    for file in files:
        if file and file.filename != '':
            filename = f"{int(time.time())}_{secure_filename(file.filename)}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            relative_url = f"/uploads/{filename}"
            cursor.execute('INSERT INTO item_images (item_id, image_path) VALUES (?, ?)', (item_id, relative_url))

    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'item_id': item_id, 'sku': sku}), 201

@app.route('/api/items/<int:item_id>', methods=['PUT'])
def update_item(item_id):
    """Updates field data for an existing inventory item."""
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE inventory SET 
            title = ?, category = ?, condition = ?, freq_range = ?,
            power_output = ?, included_acc = ?, tech_notes = ?,
            purchase_price = ?, listing_price = ?, shipping_cost = ?, status = ?
        WHERE id = ?
    ''', (
        data.get('title'),
        data.get('category'),
        data.get('condition'),
        data.get('freq_range'),
        data.get('power_output'),
        data.get('included_acc'),
        data.get('tech_notes'),
        float(data.get('purchase_price') or 0.0),
        float(data.get('listing_price') or 0.0),
        float(data.get('shipping_cost') or 0.0),
        data.get('status'),
        item_id
    ))
    
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/items/<int:item_id>/photos', methods=['POST'])
def add_photos_to_item(item_id):
    """Uploads and attaches additional photos to an existing item."""
    conn = get_db()
    cursor = conn.cursor()
    
    files = request.files.getlist('images')
    saved_photos = []
    
    for file in files:
        if file and file.filename != '':
            filename = f"{int(time.time())}_{secure_filename(file.filename)}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            relative_url = f"/uploads/{filename}"
            cursor.execute('INSERT INTO item_images (item_id, image_path) VALUES (?, ?)', (item_id, relative_url))
            saved_photos.append({'id': cursor.lastrowid, 'image_path': relative_url})

    conn.commit()
    conn.close()
    return jsonify({'status': 'success', 'added_photos': saved_photos})

@app.route('/api/photos/<int:photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    """Deletes a photo record from database and removes its file from disk."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT image_path FROM item_images WHERE id = ?', (photo_id,))
    row = cursor.fetchone()
    
    if row:
        image_path = row['image_path']
        filename = os.path.basename(image_path)
        disk_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        if os.path.exists(disk_path):
            os.remove(disk_path)
            
        cursor.execute('DELETE FROM item_images WHERE id = ?', (photo_id,))
        conn.commit()
        
    conn.close()
    return jsonify({'status': 'success'})

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
def delete_item(item_id):
    """Deletes an entire inventory record along with all associated image files from disk."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT image_path FROM item_images WHERE item_id = ?', (item_id,))
    photos = cursor.fetchall()
    
    for p in photos:
        filename = os.path.basename(p['image_path'])
        disk_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(disk_path):
            os.remove(disk_path)
            
    cursor.execute('DELETE FROM item_images WHERE item_id = ?', (item_id,))
    cursor.execute('DELETE FROM inventory WHERE id = ?', (item_id,))
    
    conn.commit()
    conn.close()
    return jsonify({'status': 'success'})

# -------------------------------------------------------------
# APPLICATION ENTRYPOINT
# -------------------------------------------------------------
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)