import csv
import io
import os
import uuid
from datetime import date, datetime, time, timedelta, timezone
from flask import Flask, Response, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from markupsafe import escape
from sqlalchemy.exc import IntegrityError

from ebay_categories import (EBAY_CATEGORY_TREE, SEPARATOR, TOP_LEVEL_NAMES, ebay_category_id,
                             is_valid_category, top_level)

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

# Categories come from eBay Canada's category list (see ebay_categories.py)
UNCATEGORIZED = '__none__'

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

    @property
    def start_date(self):
        """The day the item started selling: date listed, or date added if never listed."""
        stamp = self.date_listed or self.date_added
        return stamp.date() if stamp else None

    @property
    def days_to_sell(self):
        if self.date_sold and self.start_date:
            return max((self.date_sold - self.start_date).days, 0)
        return None

    @property
    def days_in_inventory(self):
        if self.date_added:
            return max((date.today() - self.date_added.date()).days, 0)
        return None

    @property
    def potential_profit(self):
        """Listing price minus item cost (before fees and shipping)."""
        return (self.listing_price or 0.0) - (self.item_cost or 0.0)


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
    category = (form.get('category') or '').strip()
    if not category:
        item.category = None
    elif is_valid_category(category):
        item.category = category
    # Anything else (e.g. an old pre-eBay category left unchanged) keeps the item's current value
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


@app.context_processor
def category_helpers():
    return {'ebay_category_id': ebay_category_id, 'category_separator': SEPARATOR}


def filter_by_category(query, category):
    """Filters by a full category path, a top-level name (includes all its sub-categories),
    or UNCATEGORIZED."""
    if category == UNCATEGORIZED:
        return query.filter((Item.category.is_(None)) | (Item.category == ''))
    if category in TOP_LEVEL_NAMES:
        return query.filter((Item.category == category) |
                            (Item.category.startswith(category + SEPARATOR, autoescape=True)))
    if category:
        return query.filter(Item.category == category)
    return query


def category_filter_options():
    """Options for category filter dropdowns: only categories that items actually use,
    grouped by eBay top level, plus any old-style categories under 'Other'."""
    used = {c[0] for c in db.session.query(Item.category).distinct().all() if c[0]}
    groups = []
    for top in EBAY_CATEGORY_TREE:
        subs = [s['path'] for s in top['subs'] if s['path'] in used]
        if subs or top['name'] in used:
            groups.append({'top': top['name'], 'subs': subs})
    known = {s for g in groups for s in g['subs']} | {g['top'] for g in groups}
    legacy = sorted(used - known)
    return {'groups': groups, 'legacy': legacy}


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
    query = filter_by_category(query, selected_category)

    pagination = query.order_by(Item.id.desc()).paginate(page=page, per_page=10, error_out=False)

    return render_template('index.html', pagination=pagination, search_query=search_query,
                           selected_category=selected_category, category_options=category_filter_options(),
                           uncategorized=UNCATEGORIZED)


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
            return render_template('add_item.html', categories=EBAY_CATEGORY_TREE, conditions=CONDITIONS,
                                   form=request.form), 400

        db.session.add(new_item)
        try:
            db.session.flush()  # Gets the new item ID before commit
            save_images(request.files.getlist('images'), new_item.id)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(f"SKU '{new_item.sku}' is already used by another item. Please choose a different SKU.", 'error')
            return render_template('add_item.html', categories=EBAY_CATEGORY_TREE, conditions=CONDITIONS,
                                   form=request.form), 400

        return redirect(url_for('index'))

    return render_template('add_item.html', categories=EBAY_CATEGORY_TREE, conditions=CONDITIONS, form={})


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
                page = render_template('edit_item.html', item=item, categories=EBAY_CATEGORY_TREE, conditions=CONDITIONS)
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

    return render_template('edit_item.html', item=item, categories=EBAY_CATEGORY_TREE, conditions=CONDITIONS)


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


# ==============================================================================
# Reports
# ==============================================================================

REPORT_TYPES = [('sold', 'Sold items'), ('unsold', 'Unsold items'), ('all', 'Sold & unsold')]

DATE_PRESETS = [
    ('all', 'All time'),
    ('this_month', 'This month'),
    ('last_30', 'Last 30 days'),
    ('last_90', 'Last 90 days'),
    ('this_year', 'This year'),
    ('last_year', 'Last year'),
    ('custom', 'Custom range'),
]

# Expense fields in display order (also the chart colour order)
EXPENSE_FIELDS = [
    ('item_cost', 'Item cost'),
    ('shipping_cost', 'Shipping cost'),
    ('tx_fees', 'Transaction fees'),
    ('promo_fees', 'Promo fees'),
    ('other_fees', 'Other fees'),
    ('tax_out', 'Tax paid'),
]

GROUP_BY_OPTIONS = [('top', 'Top-level category'), ('sub', 'Sub-category')]

AGE_BUCKETS = [(0, 30, '0–30 days'), (31, 60, '31–60 days'), (61, 90, '61–90 days'),
               (91, 180, '91–180 days'), (181, None, '180+ days')]


@app.template_filter('money')
def money(value):
    value = value or 0.0
    return f"-${abs(value):,.2f}" if value < 0 else f"${value:,.2f}"


def resolve_date_range(preset, start, end):
    """Turns a preset name (or custom start/end strings) into (start_date, end_date)."""
    today = date.today()
    if preset == 'this_month':
        return today.replace(day=1), today
    if preset == 'last_30':
        return today - timedelta(days=29), today
    if preset == 'last_90':
        return today - timedelta(days=89), today
    if preset == 'this_year':
        return date(today.year, 1, 1), today
    if preset == 'last_year':
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    if preset == 'custom':
        return parse_date(start), parse_date(end)
    return None, None


def get_report_filters(args):
    report_type = args.get('type', 'sold')
    if report_type not in dict(REPORT_TYPES):
        report_type = 'sold'
    preset = args.get('range', 'all')
    if preset not in dict(DATE_PRESETS):
        preset = 'all'
    start, end = resolve_date_range(preset, args.get('start'), args.get('end'))
    if start and end and start > end:
        start, end = end, start
    group_by = args.get('group', 'top')
    if group_by not in dict(GROUP_BY_OPTIONS):
        group_by = 'top'
    return {
        'type': report_type,
        'category': args.get('category', '').strip(),
        'group': group_by,
        'range': preset,
        'start': start,
        'end': end,
    }


def query_sold(filters):
    query = filter_by_category(Item.query.filter(Item.status == 'Sold'), filters['category'])
    if filters['start']:
        query = query.filter(Item.date_sold >= filters['start'])
    if filters['end']:
        query = query.filter(Item.date_sold <= filters['end'])
    return query.order_by(Item.date_sold.desc(), Item.id.desc()).all()


def query_unsold(filters):
    query = filter_by_category(
        Item.query.filter((Item.status != 'Sold') | (Item.status.is_(None))), filters['category'])
    # For unsold items the date range applies to the date they were added
    if filters['start']:
        query = query.filter(Item.date_added >= datetime.combine(filters['start'], time.min))
    if filters['end']:
        query = query.filter(Item.date_added < datetime.combine(filters['end'] + timedelta(days=1), time.min))
    return query.order_by(Item.date_added.asc(), Item.id.asc()).all()


def month_range(first, last):
    """Yields (year, month) from first to last inclusive."""
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        yield year, month
        month += 1
        if month > 12:
            year, month = year + 1, 1


def category_name(item, group_by='top'):
    if not item.category:
        return 'Uncategorized'
    return top_level(item.category) if group_by == 'top' else item.category


def build_sold_report(items, group_by='top'):
    revenue = sum(i.total_revenue for i in items)
    expenses = sum(i.total_costs for i in items)
    profit = revenue - expenses
    days = [i.days_to_sell for i in items if i.days_to_sell is not None]

    # Expense breakdown
    breakdown = []
    for field, label in EXPENSE_FIELDS:
        amount = sum(getattr(i, field) or 0.0 for i in items)
        breakdown.append({'label': label, 'amount': amount,
                          'share': (amount / expenses * 100) if expenses > 0 else 0.0})

    # Monthly totals, with empty months filled in so gaps show as zero
    monthly = []
    dated = [i for i in items if i.date_sold]
    if dated:
        by_month = {}
        for i in dated:
            key = (i.date_sold.year, i.date_sold.month)
            m = by_month.setdefault(key, {'count': 0, 'revenue': 0.0, 'expenses': 0.0})
            m['count'] += 1
            m['revenue'] += i.total_revenue
            m['expenses'] += i.total_costs
        first = min(i.date_sold for i in dated)
        last = max(i.date_sold for i in dated)
        for year, month in month_range(first, last):
            m = by_month.get((year, month), {'count': 0, 'revenue': 0.0, 'expenses': 0.0})
            monthly.append({
                'label': date(year, month, 1).strftime('%b %Y'),
                'count': m['count'],
                'revenue': round(m['revenue'], 2),
                'expenses': round(m['expenses'], 2),
                'profit': round(m['revenue'] - m['expenses'], 2),
            })

    # By category
    cats = {}
    for i in items:
        c = cats.setdefault(category_name(i, group_by), {'count': 0, 'revenue': 0.0, 'expenses': 0.0})
        c['count'] += 1
        c['revenue'] += i.total_revenue
        c['expenses'] += i.total_costs
    by_category = []
    for name, c in cats.items():
        p = c['revenue'] - c['expenses']
        by_category.append({
            'name': name, 'count': c['count'],
            'revenue': round(c['revenue'], 2), 'expenses': round(c['expenses'], 2), 'profit': round(p, 2),
            'margin': (p / c['revenue'] * 100) if c['revenue'] > 0 else 0.0,
        })
    by_category.sort(key=lambda c: c['profit'], reverse=True)

    return {
        'rows': items,
        'count': len(items),
        'revenue': revenue,
        'expenses': expenses,
        'profit': profit,
        'margin': (profit / revenue * 100) if revenue > 0 else 0.0,
        'avg_profit': (profit / len(items)) if items else 0.0,
        'avg_days_to_sell': (sum(days) / len(days)) if days else None,
        'breakdown': breakdown,
        'totals': {f: sum(getattr(i, f) or 0.0 for i in items) for f in ('item_price', 'shipping_paid', 'tax_in')},
        'monthly': monthly,
        'by_category': by_category,
    }


def build_unsold_report(items, group_by='top'):
    cost = sum(i.item_cost or 0.0 for i in items)
    listing_value = sum(i.listing_price or 0.0 for i in items)
    ages = [i.days_in_inventory for i in items if i.days_in_inventory is not None]

    cats = {}
    for i in items:
        c = cats.setdefault(category_name(i, group_by), {'count': 0, 'cost': 0.0, 'listing_value': 0.0})
        c['count'] += 1
        c['cost'] += i.item_cost or 0.0
        c['listing_value'] += i.listing_price or 0.0
    by_category = [{'name': n, 'count': c['count'], 'cost': round(c['cost'], 2),
                    'listing_value': round(c['listing_value'], 2),
                    'potential': round(c['listing_value'] - c['cost'], 2)} for n, c in cats.items()]
    by_category.sort(key=lambda c: c['cost'], reverse=True)

    age_buckets = []
    for low, high, label in AGE_BUCKETS:
        in_bucket = [i for i in items if i.days_in_inventory is not None
                     and i.days_in_inventory >= low and (high is None or i.days_in_inventory <= high)]
        age_buckets.append({'label': label, 'count': len(in_bucket),
                            'cost': round(sum(i.item_cost or 0.0 for i in in_bucket), 2)})

    # Oldest stock first
    items = sorted(items, key=lambda i: i.days_in_inventory or 0, reverse=True)

    return {
        'rows': items,
        'count': len(items),
        'listed': sum(1 for i in items if i.status == 'Listed'),
        'unlisted': sum(1 for i in items if i.status != 'Listed'),
        'cost': cost,
        'listing_value': listing_value,
        'potential': listing_value - cost,
        'avg_age': (sum(ages) / len(ages)) if ages else None,
        'by_category': by_category,
        'age_buckets': age_buckets,
    }


@app.route('/reports')
def reports():
    filters = get_report_filters(request.args)
    group_by = filters['group']
    sold = build_sold_report(query_sold(filters), group_by) if filters['type'] in ('sold', 'all') else None
    unsold = build_unsold_report(query_unsold(filters), group_by) if filters['type'] in ('unsold', 'all') else None

    chart_data = {}
    if sold:
        chart_data['monthly'] = sold['monthly']
        chart_data['soldCategories'] = sold['by_category']
    if unsold:
        chart_data['unsoldCategories'] = unsold['by_category']
        chart_data['ageBuckets'] = unsold['age_buckets']

    return render_template(
        'reports.html', filters=filters, sold=sold, unsold=unsold, chart_data=chart_data,
        report_types=REPORT_TYPES, date_presets=DATE_PRESETS, group_by_options=GROUP_BY_OPTIONS,
        category_options=category_filter_options(), uncategorized=UNCATEGORIZED,
    )


@app.route('/reports/export')
def export_report():
    """Downloads the filtered report items as a CSV file (opens in Excel)."""
    filters = get_report_filters(request.args)
    items = []
    if filters['type'] in ('sold', 'all'):
        items += query_sold(filters)
    if filters['type'] in ('unsold', 'all'):
        items += query_unsold(filters)

    def fmt_date(value):
        return value.strftime('%Y-%m-%d') if value else ''

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['SKU', 'Title', 'Category', 'eBay Category ID', 'Condition', 'Status', 'Date Added', 'Date Listed',
                     'Date Sold', 'Days To Sell', 'Days In Inventory', 'Listing Price', 'Item Price',
                     'Shipping Paid', 'Tax In', 'Total Revenue', 'TX Fees', 'Promo Fees', 'Other Fees',
                     'Item Cost', 'Shipping Cost', 'Tax Out', 'Total Costs', 'Profit', 'Margin %'])
    for i in items:
        sold_item = i.status == 'Sold'
        writer.writerow([
            i.sku, i.title, i.category or '', ebay_category_id(i.category) or '', i.condition or '', i.status or '',
            fmt_date(i.date_added), fmt_date(i.date_listed), fmt_date(i.date_sold),
            i.days_to_sell if sold_item and i.days_to_sell is not None else '',
            '' if sold_item or i.days_in_inventory is None else i.days_in_inventory,
            f"{i.listing_price or 0:.2f}", f"{i.item_price or 0:.2f}", f"{i.shipping_paid or 0:.2f}",
            f"{i.tax_in or 0:.2f}", f"{i.total_revenue:.2f}", f"{i.tx_fees or 0:.2f}",
            f"{i.promo_fees or 0:.2f}", f"{i.other_fees or 0:.2f}", f"{i.item_cost or 0:.2f}",
            f"{i.shipping_cost or 0:.2f}", f"{i.tax_out or 0:.2f}", f"{i.total_costs:.2f}",
            f"{i.profit:.2f}", f"{i.profit_margin:.1f}",
        ])

    filename = f"inventory-report-{filters['type']}-{date.today().isoformat()}.csv"
    # utf-8-sig so Excel reads accented characters correctly
    return Response(out.getvalue().encode('utf-8-sig'), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)