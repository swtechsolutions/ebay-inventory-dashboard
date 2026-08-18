import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime, timezone

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Image Upload Configuration
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

# Master category list
CATEGORIES = [
    'Clothing & Apparel',
    'Electronics',
    'Home & Kitchen',
    'Toys & Games',
    'Books & Media',
    'Sporting Goods',
    'Other'
]

# Master Condition list
CONDITIONS = ['New', 'Open Box', 'Very Good', 'Good', 'Acceptable', 'For Parts / Not Working']

# ==============================================================================
# Database Models
# ==============================================================================

class ItemImage(db.Model):
    __tablename__ = 'item_images'

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)


class Item(db.Model):
    __tablename__ = 'items'

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default='Unlisted')
    
    # New Description and Condition Fields
    condition = db.Column(db.String(50), nullable=True, default='Good')
    description = db.Column(db.Text, nullable=True)
    
    # New Date Columns
    date_added = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    date_listed = db.Column(db.DateTime, nullable=True)
    date_sold = db.Column(db.DateTime, nullable=True)
    
    # Restored Fields
    listing_price = db.Column(db.Float, default=0.0)
    date_sold = db.Column(db.Date, nullable=True)

    # Relationship for Multiple Images
    images = db.relationship('ItemImage', backref='item', cascade='all, delete-orphan', lazy=True)

    # Incoming Revenue
    item_price = db.Column(db.Float, default=0.0)
    shipping_paid = db.Column(db.Float, default=0.0)
    tax_in = db.Column(db.Float, default=0.0)

    # Outgoing Fees & Costs
    tx_fees = db.Column(db.Float, default=0.0)
    promo_fees = db.Column(db.Float, default=0.0)
    other_fees = db.Column(db.Float, default=0.0)
    item_cost = db.Column(db.Float, default=0.0)
    shipping_cost = db.Column(db.Float, default=0.0)
    tax_out = db.Column(db.Float, default=0.0)

    # Computed Properties
    @property
    def total_revenue(self):
        return (self.item_price or 0.0) + (self.shipping_paid or 0.0) + (self.tax_in or 0.0)

    @property
    def total_costs(self):
        return (
            (self.tx_fees or 0.0) +
            (self.promo_fees or 0.0) +
            (self.other_fees or 0.0) +
            (self.item_cost or 0.0) +
            (self.shipping_cost or 0.0) +
            (self.tax_out or 0.0)
        )

    @property
    def profit(self):
        return self.total_revenue - self.total_costs

    @property
    def profit_margin(self):
        revenue = self.total_revenue
        return (self.profit / revenue) * 100 if revenue > 0 else 0.0


# ==============================================================================
# Helper Functions
# ==============================================================================

def parse_float(val):
    try:
        return float(val) if val else 0.0
    except (ValueError, TypeError):
        return 0.0

def parse_date(val):
    try:
        return datetime.strptime(val, '%Y-%m-%d').date() if val else None
    except (ValueError, TypeError):
        return None

def save_images(file_list, item_id):
    """Saves multiple files to static/uploads and links them to the Item."""
    for file_obj in file_list:
        if file_obj and file_obj.filename != '':
            ext = file_obj.filename.rsplit('.', 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                filename = secure_filename(file_obj.filename)
                unique_filename = f"{int(datetime.now().timestamp())}_{filename}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file_obj.save(file_path)
                
                # Save database record
                new_image = ItemImage(item_id=item_id, image_path=f"uploads/{unique_filename}")
                db.session.add(new_image)


# ==============================================================================
# Routes
# ==============================================================================

@app.route('/')
def index():
    search_query = request.args.get('q', '').strip()
    selected_category = request.args.get('category', '').strip()
    page = request.args.get('page', 1, type=int)

    query = Item.query

    if search_query:
        query = query.filter((Item.title.ilike(f"%{search_query}%")) | (Item.sku.ilike(f"%{search_query}%")))
    if selected_category:
        query = query.filter(Item.category == selected_category)

    pagination = query.order_by(Item.id.desc()).paginate(page=page, per_page=10, error_out=False)
    categories = [cat[0] for cat in db.session.query(Item.category).distinct().all() if cat[0]]

    return render_template('index.html', pagination=pagination, search_query=search_query, selected_category=selected_category, categories=categories)


@app.route('/add', methods=['GET', 'POST'])
def add_item():
    if request.method == 'POST':
        
        status = request.form.get('status', 'Unlisted')
        
        # Set timestamps based on initial status
        now = datetime.now(timezone.utc)
        date_listed = now if status == 'Listed' else None
        date_sold = now if status == 'Sold' else None
        
        new_item = Item(
            sku=request.form.get('sku'),
            title=request.form.get('title'),
            category=request.form.get('category'),
            condition=request.form.get('condition'),
            description=request.form.get('description'),
            status = request.form.get('status', 'Unlisted'),
            date_listed = date_listed,
            date_sold = date_sold,
            listing_price=float(request.form.get('listing_price', 0.0) or 0.0),
            item_price=parse_float(request.form.get('item_price')),
            shipping_paid=parse_float(request.form.get('shipping_paid')),
            tax_in=parse_float(request.form.get('tax_in')),
            tx_fees=parse_float(request.form.get('tx_fees')),
            promo_fees=parse_float(request.form.get('promo_fees')),
            other_fees=parse_float(request.form.get('other_fees')),
            item_cost=float(request.form.get('item_cost', 0.0) or 0.0),
            shipping_cost=parse_float(request.form.get('shipping_cost')),
            tax_out=parse_float(request.form.get('tax_out'))
        )
        db.session.add(new_item)
        db.session.flush()  # Gets the new item ID before commit

        # Handle multiple uploaded image files
        uploaded_files = request.files.getlist('images')
        save_images(uploaded_files, new_item.id)

        db.session.commit()
        return redirect(url_for('index'))

    return render_template('add_item.html', categories=CATEGORIES, conditions=CONDITIONS)


@app.route('/edit/<int:item_id>', methods=['GET', 'POST'])
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)

    if request.method == 'POST':

        # Get status from form and strip accidental spaces
        new_status = request.form.get('status', '').strip()
        old_status = item.status

        now = datetime.now(timezone.utc)

        # Handle Date Listed
        if new_status == 'Listed' and old_status != 'Listed':
            item.date_listed = now
        elif new_status == 'Unlisted':
            item.date_listed = None

        # Handle Date Sold
        if new_status == 'Sold':
            # Stamp date_sold if it isn't already set
            if item.date_sold is None or old_status != 'Sold':
                item.date_sold = now
        else:
            # Clear date_sold if item status moves away from Sold
            item.date_sold = None
        
        item.sku = request.form.get('sku')
        item.title = request.form.get('title')
        item.category = request.form.get('category')
        item.condition = request.form.get('condition')
        item.description = request.form.get('description')
        item.status = request.form.get('status')
        item.status = new_status
        item.listing_price = parse_float(request.form.get('listing_price'))
        item.date_sold = item.date_sold 

        item.item_price = parse_float(request.form.get('item_price'))
        item.shipping_paid = parse_float(request.form.get('shipping_paid'))
        item.tax_in = parse_float(request.form.get('tax_in'))

        item.tx_fees = parse_float(request.form.get('tx_fees'))
        item.promo_fees = parse_float(request.form.get('promo_fees'))
        item.other_fees = parse_float(request.form.get('other_fees'))
        item.item_cost = parse_float(request.form.get('item_cost'))
        item.shipping_cost = parse_float(request.form.get('shipping_cost'))
        item.tax_out = parse_float(request.form.get('tax_out'))

        # Add newly uploaded images to the existing set
        uploaded_files = request.files.getlist('images')
        save_images(uploaded_files, item.id)

        db.session.commit()
        return redirect(url_for('view_item', item_id=item.id))

    return render_template('edit_item.html', item=item, categories=CATEGORIES, conditions=CONDITIONS)


@app.route('/delete-image/<int:image_id>', methods=['POST'])
def delete_image(image_id):
    """Deletes an image file from disk and database."""
    image = ItemImage.query.get_or_404(image_id)
    item_id = image.item_id

    # Remove physical file from disk
    file_path = os.path.join(app.root_path, 'static', image.image_path)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(image)
    db.session.commit()
    return redirect(url_for('edit_item', item_id=item_id))


@app.route('/item/<int:item_id>')
def view_item(item_id):
    item = Item.query.get_or_404(item_id)
    return render_template('view_item.html', item=item)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)