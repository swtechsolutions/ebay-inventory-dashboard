// Search box for the eBay category dropdown: typing narrows the list to matching
// categories (matches the top-level or sub-category name; every word must match).
(function () {
    document.querySelectorAll('[data-category-picker]').forEach(function (picker) {
        var search = picker.querySelector('[data-category-search]');
        var select = picker.querySelector('[data-category-select]');
        var status = picker.querySelector('[data-category-status]');

        // Remember the full list once: loose options (placeholder / old category) and groups
        var loose = [];
        var groups = [];
        Array.prototype.forEach.call(select.children, function (el) {
            if (el.tagName === 'OPTGROUP') {
                groups.push({
                    label: el.label,
                    options: Array.prototype.map.call(el.children, function (o) {
                        return { value: o.value, text: o.textContent };
                    }),
                });
            } else {
                loose.push({ value: el.value, text: el.textContent });
            }
        });

        var autoPicked = null;  // a match chosen for the user, replaced as they keep typing

        function option(value, text, selectedValue) {
            var o = document.createElement('option');
            o.value = value;
            o.textContent = text;
            if (value === selectedValue) o.selected = true;
            return o;
        }

        function render() {
            var words = search.value.toLowerCase().split(/\s+/).filter(Boolean);
            var current = select.value === autoPicked ? '' : select.value;
            var matches = 0, firstMatch = null;

            select.textContent = '';
            loose.forEach(function (o) { select.appendChild(option(o.value, o.text, current)); });

            groups.forEach(function (g) {
                var opts = g.options.filter(function (o) {
                    var hay = (g.label + ' ' + o.text).toLowerCase();
                    return words.every(function (w) { return hay.indexOf(w) !== -1; });
                });
                // Keep the currently selected category visible even if it doesn't match
                if (!opts.length && !g.options.some(function (o) { return o.value === current; })) return;
                if (!opts.some(function (o) { return o.value === current; })) {
                    g.options.forEach(function (o) { if (o.value === current) opts.unshift(o); });
                }
                var og = document.createElement('optgroup');
                og.label = g.label;
                opts.forEach(function (o) {
                    og.appendChild(option(o.value, o.text, current));
                    if (o.value !== current) { matches++; if (!firstMatch) firstMatch = o.value; }
                });
                select.appendChild(og);
            });

            autoPicked = null;
            if (!words.length) {
                status.textContent = '';
            } else if (matches === 0) {
                status.textContent = 'No categories match "' + search.value + '".';
            } else {
                status.textContent = matches + ' matching categor' + (matches === 1 ? 'y' : 'ies') + '. Pick one from the list.';
                // With nothing chosen yet, pre-select the first match to save a click
                if (!current) { select.value = firstMatch; autoPicked = firstMatch; }
            }
        }

        search.addEventListener('input', render);
        select.addEventListener('change', function () { autoPicked = null; });
        // Enter in the search box shouldn't submit the whole item form
        search.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); select.focus(); }
        });
    });
})();
