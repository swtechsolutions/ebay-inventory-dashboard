import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure Upload Folder
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)

# -----------------------------------------------------------------------------
# Database Models
# -----------------------------------------------------------------------------

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=True)
    condition = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    
    purchase_price = db.Column(db.Float, default=0.0)
    listing_price = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Draft')  # Draft, Active, Sold
    
    # Financials for sold items
    sold_price = db.Column(db.Float, default=0.0)
    buyer_shipping = db.Column(db.Float, default=0.0)
    buyer_tax = db.Column(db.Float, default=0.0)
    transaction_fees = db.Column(db.Float, default=0.0)
    promotional_fees = db.Column(db.Float, default=0.0)
    actual_shipping_cost = db.Column(db.Float, default=0.0)
    sold_date = db.Column(db.String(20), nullable=True)

    # Relationships
    images = db.relationship('ItemImage', backref='item', cascade='all, delete-orphan', lazy=True)

    @property
    def primary_image(self):
        """Returns relative path of the first image or None."""
        if self.images:
            return self.images[0].image_path
        return None


class ItemImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    image_path = db.Column(db.String(300), nullable=False)


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def allowed_file(filename):
    """Validates if the uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_next_sku():
    """
    Generates the next sequential SKU in the format SW1XXXX.
    Starts at SW10001 if no items exist in the database.
    """
    last_item = Item.query.order_by(Item.id.desc()).first()
    
    if not last_item:
        next_number = 1
    else:
        next_number = last_item.id + 1
        
    # Format: SW1 followed by a 4-digit zero-padded number (e.g., SW10001)
    return f"SW1{next_number:04d}"


# -----------------------------------------------------------------------------
# Application Routes
# -----------------------------------------------------------------------------

@app.route('/')
def index():
    """Main inventory dashboard list."""
    items = Item.query.order_by(Item.id.desc()).all()
    for item in items:
        item.image_path = item.primary_image
    return render_template('index.html', items=items)


def generate_ebay_html(item):
    """
    Builds a standalone HTML snippet styled for eBay listing descriptions.
    """
    description_formatted = (item.description or 'No description provided.').replace('\n', '<br>')
    
    ebay_html = f"""<div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
    <h1 style="font-size: 24px; color: #111827; margin-bottom: 12px;">{item.title}</h1>
    <div style="background-color: #f3f4f6; padding: 10px 15px; border-radius: 6px; margin-bottom: 20px;">
        <strong>SKU:</strong> {item.sku} &nbsp;|&nbsp;
        <strong>Condition:</strong> {item.condition or 'Not specified'} &nbsp;|&nbsp;
        <strong>Category:</strong> {item.category or 'General'}
    </div>
    <h3 style="font-size: 18px; color: #374151; border-bottom: 2px solid #2563eb; padding-bottom: 5px;">Item Description</h3>
    <div style="font-size: 15px; line-height: 1.6; color: #4b5563; margin-top: 15px;">
        {description_formatted}
    </div>
</div>"""
    return ebay_html


@app.route('/item/<int:item_id>')
def view_item(item_id):
    """View detailed information for a single item + eBay HTML snippet."""
    item = Item.query.get_or_404(item_id)
    images = ItemImage.query.filter_by(item_id=item.id).all()
    
    # Calculate Net Profit if the item is sold
    net_profit = 0.0
    if item.status == 'Sold':
        gross_revenue = (item.sold_price or 0.0) + (item.buyer_shipping or 0.0)
        total_costs = (
            (item.purchase_price or 0.0) + 
            (item.transaction_fees or 0.0) + 
            (item.promotional_fees or 0.0) + 
            (item.actual_shipping_cost or 0.0)
        )
        net_profit = gross_revenue - total_costs

    # Generate eBay HTML snippet
    ebay_html = generate_ebay_html(item)

    return render_template('view_item.html', item=item, images=images, net_profit=net_profit, ebay_html=ebay_html)


@app.route('/add_item', methods=['GET', 'POST'])
def add_item():
    """Create a new inventory item with optional auto-generated SW1XXXX SKU."""
    if request.method == 'POST':
        # Auto-generate SKU if left blank by user
        user_sku = request.form.get('sku')
        sku = user_sku.strip() if user_sku and user_sku.strip() else generate_next_sku()

        title = request.form.get('title')
        category = request.form.get('category')
        condition = request.form.get('condition')
        description = request.form.get('description')
        purchase_price = float(request.form.get('purchase_price') or 0.0)
        listing_price = float(request.form.get('listing_price') or 0.0)
        status = request.form.get('status') or 'Draft'

        new_item = Item(
            sku=sku,
            title=title,
            category=category,
            condition=condition,
            description=description,
            purchase_price=purchase_price,
            listing_price=listing_price,
            status=status
        )
        db.session.add(new_item)
        db.session.commit()

        # Upload files
        files = request.files.getlist('images')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{new_item.id}_{file.filename}")
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)

                relative_path = f"uploads/{filename}"
                img_record = ItemImage(item_id=new_item.id, image_path=relative_path)
                db.session.add(img_record)

        db.session.commit()
        flash(f'Item {sku} created successfully!', 'success')
        return redirect(url_for('index'))

    # GET request: send the next suggested SKU placeholder
    suggested_sku = generate_next_sku()
    return render_template('edit_item.html', item=None, images=[], suggested_sku=suggested_sku)


@app.route('/edit_item/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    """Edit item details and upload new photos."""
    item = Item.query.get_or_404(item_id)

    if request.method == 'POST':
        user_sku = request.form.get('sku')
        if user_sku and user_sku.strip():
            item.sku = user_sku.strip()

        item.title = request.form.get('title')
        item.category = request.form.get('category')
        item.condition = request.form.get('condition')
        item.description = request.form.get('description')
        item.purchase_price = float(request.form.get('purchase_price') or 0.0)
        item.listing_price = float(request.form.get('listing_price') or 0.0)
        item.status = request.form.get('status')

        # Financial fields
        item.sold_price = float(request.form.get('sold_price') or 0.0)
        item.buyer_shipping = float(request.form.get('buyer_shipping') or 0.0)
        item.buyer_tax = float(request.form.get('buyer_tax') or 0.0)
        item.transaction_fees = float(request.form.get('transaction_fees') or 0.0)
        item.promotional_fees = float(request.form.get('promotional_fees') or 0.0)
        item.actual_shipping_cost = float(request.form.get('actual_shipping_cost') or 0.0)
        item.sold_date = request.form.get('sold_date')

        # Handle newly uploaded images
        files = request.files.getlist('images')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{item.id}_{file.filename}")
                save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(save_path)

                relative_path = f"uploads/{filename}"
                img_record = ItemImage(item_id=item.id, image_path=relative_path)
                db.session.add(img_record)

        db.session.commit()
        flash('Item updated successfully!', 'success')
        return redirect(url_for('view_item', item_id=item.id))

    images = ItemImage.query.filter_by(item_id=item.id).all()
    return render_template('edit_item.html', item=item, images=images)


@app.route('/delete_image/<int:image_id>', methods=['POST'])
def delete_image(image_id):
    """Delete an image file from disk and database."""
    image = ItemImage.query.get_or_404(image_id)
    item_id = image.item_id

    # Delete physical file from uploads folder
    file_path = os.path.join(app.root_path, 'static', image.image_path)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            print(f"Error removing file {file_path}: {e}")

    # Remove database record
    db.session.delete(image)
    db.session.commit()

    flash('Image deleted successfully.', 'success')
    return redirect(url_for('edit_item', item_id=item_id))


@app.route('/delete_item/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    """Delete an entire item and all associated image files."""
    item = Item.query.get_or_404(item_id)
    
    # Delete image files from disk
    for img in item.images:
        file_path = os.path.join(app.root_path, 'static', img.image_path)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass

    db.session.delete(item)
    db.session.commit()
    flash('Item deleted successfully.', 'success')
    return redirect(url_for('index'))


# Create database tables if they do not exist
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)