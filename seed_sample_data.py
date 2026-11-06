"""Adds sample (demo) inventory items for trying out the app, the reports, and testing changes.

Every sample item has a SKU starting with "DEMO-", so they can be removed again
without touching your real items.

Usage (from the project folder, with the virtual environment activated):
    python seed_sample_data.py            # add the sample items (skips any that already exist)
    python seed_sample_data.py --reset    # remove all sample items, then add them fresh
    python seed_sample_data.py --remove   # remove all sample items

Dates are set relative to today, so the reports always show recent activity.
Fees are approximate (about 13.6% of the sale plus $0.40) and sales tax collected
equals tax paid, as when eBay collects and remits it.
"""
import argparse
import os
import sys
from datetime import date, datetime, time, timedelta

from app import app, db, Item
from ebay_categories import is_valid_category

PREFIX = 'DEMO-'
TAX_RATE = 0.13

# Each sample:
#  sku, title, category, condition, status,
#  added (days ago), listed (days after added, None = not listed), sold (days after listed, None = not sold),
#  listing price, sold price, shipping paid by buyer, item cost, shipping cost, promo rate, other fees, description
SAMPLES = [
    # --- Sold -----------------------------------------------------------------------------------------
    ('DEMO-1001', 'Lenovo ThinkPad T480 14" i5-8350U 16GB 256GB SSD Win 11 Pro',
     'Computers/Tablets & Networking > Laptops & Netbooks', 'Good', 'Sold',
     300, 2, 9, 389.99, 375.00, 0.00, 180.00, 24.50, 0.05, 0.00,
     "Business-class laptop, fully tested.\nIntel i5-8350U, 16GB RAM, 256GB NVMe SSD.\nBattery holds about 4 hours.\nLight wear on the lid; screen is clean."),
    ('DEMO-1002', 'Samsung 860 EVO 500GB 2.5" SATA SSD MZ-76E500',
     'Computers/Tablets & Networking > Drives, Storage & Blank Media', 'Very Good', 'Sold',
     280, 1, 6, 64.99, 59.99, 8.99, 22.00, 7.85, 0.00, 0.00,
     "Health 98% (CrystalDiskInfo screenshot in photos).\nSecurely wiped."),
    ('DEMO-1003', 'Seagate BarraCuda 2TB 3.5" SATA HDD 7200RPM ST2000DM008',
     'Computers/Tablets & Networking > Drives, Storage & Blank Media', 'Good', 'Sold',
     250, 3, 21, 54.99, 49.99, 12.99, 15.00, 14.20, 0.03, 0.00,
     "Passed full SMART and surface test. 11,000 power-on hours."),
    ('DEMO-1004', 'Logitech MX Master 3 Wireless Mouse - Graphite',
     'Computers/Tablets & Networking > Keyboards, Mice & Pointers', 'Very Good', 'Sold',
     220, 1, 4, 79.99, 79.99, 0.00, 35.00, 9.10, 0.00, 0.00,
     "Includes USB receiver and charging cable."),
    ('DEMO-1005', 'Pink Floyd - The Dark Side of the Moon LP Vinyl 1973 Harvest SHVL 804',
     'Music > Vinyl Records', 'Good', 'Sold',
     210, 2, 30, 129.99, 115.00, 15.00, 20.00, 16.75, 0.08, 0.00,
     "UK pressing with both posters and stickers.\nVinyl: VG+, light surface marks, plays through without skips.\nSleeve: VG, ring wear & small seam split (see photos)."),
    ('DEMO-1006', 'Fleetwood Mac - Rumours LP 1977 Warner Bros BSK 3010',
     'Music > Vinyl Records', 'Very Good', 'Sold',
     190, 1, 12, 39.99, 37.50, 15.00, 8.00, 16.75, 0.00, 0.00,
     "Original inner sleeve. Plays great."),
    ('DEMO-1007', 'Nintendo Switch OLED Console 64GB - White',
     'Video Games & Consoles > Video Game Consoles', 'Very Good', 'Sold',
     175, 1, 3, 349.99, 340.00, 0.00, 250.00, 22.40, 0.05, 0.00,
     "Console, dock, Joy-Cons, grip, HDMI and power cable. Screen protector since day one."),
    ('DEMO-1008', 'The Legend of Zelda: Tears of the Kingdom (Nintendo Switch)',
     'Video Games & Consoles > Video Games', 'Very Good', 'Sold',
     160, 0, 2, 59.99, 55.00, 5.99, 30.00, 5.25, 0.00, 0.00,
     "Cartridge and case, tested."),
    ('DEMO-1009', 'LEGO Star Wars 75192 Millennium Falcon UCS - Complete with Box',
     'Toys & Hobbies > Building Toys', 'Good', 'Sold',
     150, 4, 25, 899.99, 850.00, 0.00, 520.00, 68.00, 0.08, 0.00,
     "100% complete, verified piece by piece.\nAll minifigures included.\nBox has shelf wear; instructions like new."),
    ('DEMO-1010', 'Vintage Pyrex 403 Butterprint Mixing Bowl Turquoise on White',
     'Home & Garden > Kitchen, Dining & Bar', 'Good', 'Sold',
     140, 2, 18, 34.99, 30.00, 18.00, 6.00, 19.40, 0.00, 0.00,
     "No chips or cracks. Light utensil marks inside."),
    ('DEMO-1011', 'DeWalt DCD771 20V MAX Cordless Drill Driver (Tool Only)',
     'Home & Garden > Tools & Workshop Equipment', 'Good', 'Sold',
     120, 1, 7, 69.99, 65.00, 14.99, 30.00, 15.60, 0.00, 0.00,
     "Tool only, no battery or charger. Chuck and clutch work perfectly."),
    ('DEMO-1012', 'Patagonia Better Sweater 1/4 Zip Fleece Men\'s Large - Navy',
     'Clothing, Shoes & Accessories > Men', 'Very Good', 'Sold',
     100, 1, 10, 74.99, 70.00, 12.00, 12.00, 11.35, 0.05, 0.00,
     "Pit to pit 24\", length 28\". No pilling or stains."),
    ('DEMO-1013', 'Canon EF 50mm f/1.8 STM Lens',
     'Cameras & Photo > Lenses & Filters', 'Very Good', 'Sold',
     80, 1, 5, 149.99, 145.00, 0.00, 85.00, 12.30, 0.00, 0.00,
     "Clean glass, no haze or fungus. Front and rear caps included."),
    ('DEMO-1014', 'Apple iPad Air 4th Gen 64GB Wi-Fi Sky Blue - Cracked Screen (For Parts)',
     'Computers/Tablets & Networking > Tablets & eBook Readers', 'For Parts / Not Working', 'Sold',
     70, 1, 14, 119.99, 95.00, 0.00, 110.00, 13.75, 0.00, 2.50,
     "Sold as-is for parts: cracked digitizer, powers on, iCloud unlocked.\nNo returns on parts items."),  # a loss
    ('DEMO-1015', '1967 Canadian Centennial Silver Dollar Goose Coin',
     'Coins & Paper Money > Coins: Canada', 'Very Good', 'Sold',
     55, 1, 8, 44.99, 42.00, 3.50, 25.00, 3.10, 0.00, 0.00,
     "80% silver. Uncirculated, in 2x2 holder."),
    ('DEMO-1016', 'Sony WH-1000XM4 Wireless Noise Cancelling Headphones - Black',
     'Consumer Electronics > Portable Audio & Headphones', 'Good', 'Sold',
     40, 1, 4, 199.99, 189.99, 0.00, 110.00, 14.80, 0.05, 0.00,
     "Ear pads replaced with new genuine pads. Case & cable included."),
    ('DEMO-1017', 'Raspberry Pi 4 Model B 4GB with Case and Power Supply',
     'Computers/Tablets & Networking > Other Computers & Networking', 'Very Good', 'Sold',
     25, 0, 3, 89.99, 89.99, 9.99, 55.00, 8.20, 0.00, 0.00,
     "Booted and tested with Raspberry Pi OS. 32GB microSD included."),
    ('DEMO-1018', 'Hot Wheels Redline 1969 Custom Fleetside Purple',
     'Toys & Hobbies > Diecast & Toy Vehicles', 'Acceptable', 'Sold',
     12, 0, 2, 59.99, 54.00, 4.50, 5.00, 3.90, 0.00, 0.00,
     "Play wear & chipped paint (see photos). Wheels roll straight."),
    # --- Listed, not sold yet -------------------------------------------------------------------------
    ('DEMO-2001', 'Dell OptiPlex 7070 Micro i5-9500T 16GB 512GB SSD Win 11 Pro',
     'Computers/Tablets & Networking > Desktops & All-In-Ones', 'Very Good', 'Listed',
     45, 2, None, 279.99, 0, 0, 140.00, 0, 0, 0,
     "Tiny form factor, fully tested. Power adapter included."),
    ('DEMO-2002', 'Netgear Nighthawk R7000 AC1900 Wi-Fi Router',
     'Computers/Tablets & Networking > Home Networking & Connectivity', 'Good', 'Listed',
     95, 3, None, 59.99, 0, 0, 20.00, 0, 0, 0,
     "Factory reset, latest firmware. Power adapter included."),
    ('DEMO-2003', 'The Beatles - Abbey Road LP 1969 Apple Records SO-383',
     'Music > Vinyl Records', 'Good', 'Listed',
     130, 1, None, 89.99, 0, 0, 15.00, 0, 0, 0,
     "Canadian Apple pressing. VG / VG."),
    ('DEMO-2004', 'Fender Squier Classic Vibe 50s Stratocaster - 2-Tone Sunburst',
     'Musical Instruments & Gear > Guitars & Basses', 'Very Good', 'Listed',
     60, 3, None, 549.99, 0, 0, 380.00, 0, 0, 0,
     "Fresh strings and setup. Neck is straight, frets have plenty of life left."),
    ('DEMO-2005', 'Pokemon Base Set Charizard 4/102 Holo Unlimited (Played)',
     'Toys & Hobbies > Collectible Card Games', 'Acceptable', 'Listed',
     210, 5, None, 299.99, 0, 0, 200.00, 0, 0, 0,
     "Heavy play: whitening on edges, light crease on back (see photos)."),  # aging stock
    ('DEMO-2006', 'KitchenAid Artisan Stand Mixer 5qt KSM150 - Empire Red',
     'Home & Garden > Kitchen, Dining & Bar', 'Good', 'Listed',
     20, 1, None, 279.99, 0, 0, 120.00, 0, 0, 0,
     "Runs smoothly at all speeds. Bowl, flat beater, dough hook & whisk included."),
    ('DEMO-2007', 'Garmin Forerunner 245 GPS Running Watch - Slate',
     'Cell Phones & Accessories > Smart Watches', 'Good', 'Listed',
     8, 0, None, 149.99, 0, 0, 90.00, 0, 0, 0,
     "Battery still lasts about 5 days. Charging cable included."),
    # --- Not listed yet --------------------------------------------------------------------------------
    ('DEMO-3001', 'Corsair Vengeance LPX 32GB (2x16GB) DDR4 3200 Desktop RAM',
     'Computers/Tablets & Networking > Computer Components & Parts', 'Very Good', 'Unlisted',
     15, None, None, 79.99, 0, 0, 35.00, 0, 0, 0,
     "Tested with MemTest86, 4 passes, 0 errors."),
    ('DEMO-3002', 'Box Lot of 25 Assorted Hardcover Mystery Novels',
     'Books & Magazines > Books', 'Good', 'Unlisted',
     35, None, None, 49.99, 0, 0, 10.00, 0, 0, 0,
     "Agatha Christie, Louise Penny, Michael Connelly & more.\nHeavy box: ships by Canada Post ground."),
    ('DEMO-3003', 'Royal Albert Old Country Roses 5-Piece Place Setting',
     'Pottery & Glass > Decorative Cookware, Dinnerware & Serveware', 'Very Good', 'Unlisted',
     190, None, None, 89.99, 0, 0, 25.00, 0, 0, 0,
     "Made in England, first quality. No chips or crazing."),  # sitting a long time
    ('DEMO-3004', 'Assorted Electronics Parts Lot - Cables, Adapters & Chargers',
     None, 'Acceptable', 'Unlisted',
     5, None, None, 0.00, 0, 0, 5.00, 0, 0, 0,
     "Unsorted lot, needs sorting and pricing."),  # no category / no price yet
    ('DEMO-3005', 'Special characters test: Mugs & Cups <Set of 4> "Vintage" 50% Off',
     'Home & Garden > Kitchen, Dining & Bar', 'Good', 'Unlisted',
     2, None, None, 24.99, 0, 0, 6.00, 0, 0, 0,
     "Tests HTML escaping: <b>not bold</b> & ampersands.\n\nBlank line above, \"quotes\" and 'apostrophes'."),
]


def stamp(days_ago):
    """A datetime `days_ago` days before today (mid-morning, so dates don't shift across time zones)."""
    return datetime.combine(date.today() - timedelta(days=days_ago), time(14, 0))


def build_item(sample):
    (sku, title, category, condition, status, added_ago, listed_after, sold_after, listing_price,
     sold_price, ship_paid, item_cost, ship_cost, promo_rate, other_fees, description) = sample

    if category is not None and not is_valid_category(category):
        raise ValueError(f"{sku}: '{category}' is not an eBay category in data/ebay_categories_ca.txt")

    added = stamp(added_ago)
    listed = added + timedelta(days=listed_after) if listed_after is not None else None
    item = Item(sku=sku, title=title, category=category, condition=condition, status=status,
                description=description, date_added=added, date_listed=listed,
                listing_price=listing_price, item_cost=item_cost)

    if status == 'Sold':
        sold_on = (listed + timedelta(days=sold_after)).date()
        item.date_sold = min(sold_on, date.today())
        item.item_price = sold_price
        item.shipping_paid = ship_paid
        sale_total = sold_price + ship_paid
        item.tax_in = round(sale_total * TAX_RATE, 2)
        item.tax_out = item.tax_in  # eBay collects and remits the tax
        item.tx_fees = round(sale_total * 0.136 + 0.40, 2)
        item.promo_fees = round(sold_price * promo_rate, 2)
        item.other_fees = other_fees
        item.shipping_cost = ship_cost
    return item


def remove_samples():
    items = Item.query.filter(Item.sku.startswith(PREFIX, autoescape=True)).all()
    for item in items:
        # Delete any photos added to a sample item from disk too
        for image in item.images:
            path = os.path.join(app.root_path, 'static', image.image_path)
            if os.path.isfile(path):
                os.remove(path)
        db.session.delete(item)  # photo records are deleted with the item
    db.session.commit()
    return len(items)


def add_samples():
    existing = {sku for (sku,) in db.session.query(Item.sku).filter(Item.sku.startswith(PREFIX, autoescape=True))}
    added = 0
    for sample in SAMPLES:
        if sample[0] in existing:
            continue
        db.session.add(build_item(sample))
        added += 1
    db.session.commit()
    return added, len(existing)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--reset', action='store_true', help='remove all sample items, then add them fresh')
    group.add_argument('--remove', action='store_true', help='remove all sample items')
    args = parser.parse_args()

    with app.app_context():
        db.create_all()
        if args.remove or args.reset:
            print(f"Removed {remove_samples()} sample item(s).")
        if args.remove:
            return 0
        added, skipped = add_samples()
        print(f"Added {added} sample item(s)." + (f" {skipped} already existed and were left as-is." if skipped else ""))
        sold = sum(1 for s in SAMPLES if s[4] == 'Sold')
        print(f"Samples: {sold} sold, {len(SAMPLES) - sold} unsold, across "
              f"{len({s[2] for s in SAMPLES if s[2]})} eBay categories.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
