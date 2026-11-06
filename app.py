import os
import uuid
from datetime import date, datetime, timezone
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from markupsafe import escape
from sqlalchemy.exc import IntegrityError

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
    date_sold = db.Column(db.Date, nullable=True)  # Date only (matches existing DB schema)

    listing_price = db.Column(db.Float, default=0.0)

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
        if file_obj and file_obj.filename and '.' in file_obj.filename:
            ext = file_obj.filename.rsplit('.', 1)[-1].lower()
            if ext in ALLOWED_EXTENSIONS:
                # Random name so uploads never collide or lose their extension
                unique_filename = f"{uuid.uuid4().hex}.{ext}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                file_obj.save(file_path)
                
                # Save database record
                new_image = ItemImage(item_id=item_id, image_path=f"uploads/{unique_filename}")
                db.session.add(new_image)


def sku_taken(sku, exclude_id=None):
    """True if another item already uses this SKU."""
    with db.session.no_autoflush:
        query = Item.query.filter(Item.sku == sku)
        if exclude_id is not None:
            query = query.filter(Item.id != exclude_id)
        return db.session.query(query.exists()).scalar()


def apply_form(item, form):
    """Copies the editable text and money fields from a submitted form onto an Item."""
    item.sku = (form.get('sku') or '').strip()
    item.title = (form.get('title') or '').strip()
    item.category = form.get('category')
    item.condition = form.get('condition')
    item.description = form.get('description')
    for field in ('listing_price', 'item_price', 'shipping_paid', 'tax_in',
                  'tx_fees', 'promo_fees', 'other_fees', 'item_cost',
                  'shipping_cost', 'tax_out'):
        # Fields missing from a form (e.g. revenue fields on the add page) stay unchanged
        if field in form:
            setattr(item, field, parse_float(form.get(field)))


@app.template_filter('ebay_html')
def ebay_html(text):
    """Turns plain text into HTML for the eBay description: escapes it and keeps line breaks."""
    if not text:
        return ''
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return str(escape(text)).replace('\n', '<br>\n')


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
        status = request.form.get('status', 'Unlisted').strip()

        new_item = Item(status=status)
        apply_form(new_item, request.form)

        # Set dates based on initial status
        new_item.date_listed = datetime.now(timezone.utc) if status == 'Listed' else None
        new_item.date_sold = date.today() if status == 'Sold' else None

        if sku_taken(new_item.sku):
            flash(f"SKU '{new_item.sku}' is already used by another item. Please choose a different SKU.", 'error')
            return render_template('add_item.html', categories=CATEGORIES, conditions=CONDITIONS,
                                   form=request.form), 400

        db.session.add(new_item)
        try:
            db.session.flush()  # Gets the new item ID before commit
            save_images(request.files.getlist('images'), new_item.id)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(f"SKU '{new_item.sku}' is already used by another item. Please choose a different SKU.", 'error')
            return render_template('add_item.html', categories=CATEGORIES, conditions=CONDITIONS,
                                   form=request.form), 400

        return redirect(url_for('index'))

    return render_template('add_item.html', categories=CATEGORIES, conditions=CONDITIONS, form={})


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
            picked_date = parse_date(request.form.get('date_sold'))
            if picked_date:
                # Use the date chosen in the form
                item.date_sold = picked_date
            elif item.date_sold is None or old_status != 'Sold':
                # No date chosen: stamp today when the item becomes Sold
                item.date_sold = date.today()
        else:
            # Clear date_sold if item status moves away from Sold
            item.date_sold = None

        item.status = new_status
        apply_form(item, request.form)

        if sku_taken(item.sku, exclude_id=item.id):
            flash(f"SKU '{item.sku}' is already used by another item. Please choose a different SKU.", 'error')
            # Re-show the form with the user's edits, then discard them
            with db.session.no_autoflush:
                page = render_template('edit_item.html', item=item, categories=CATEGORIES, conditions=CONDITIONS)
            db.session.rollback()
            return page, 400

        try:
            # Add newly uploaded images to the existing set
            save_images(request.files.getlist('images'), item.id)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(f"SKU '{request.form.get('sku', '').strip()}' is already used by another item. Please choose a different SKU.", 'error')
            return redirect(url_for('edit_item', item_id=item_id))

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