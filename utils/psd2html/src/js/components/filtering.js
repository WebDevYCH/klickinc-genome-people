export default function initFiltering() {
	const hiddenClass = 'hidden';
	const lastClass = 'last';

	jQuery('.genome-main-content').each(function() {
		const holder = jQuery(this);
		const filterPanel = holder.find('.genome-filter-bar');
		const list = holder.find('.users-tree-menu');
		const filterItems = list.find('li');
		const allCheckbox = list.find(':checkbox');
		const dateField = holder.find('.datepicker');
		const freelanceersField = holder.find('[name="check-freelanceers"]');
		const freelanceersItems = holder.find('.freelanceer');
		const btnSetDate = holder.find('.set-to-today');
		let activeFilters = {};
		let activeItems = null;

		if (!filterItems.length && !filterItems.length && !filterPanel.length) return;

		const filterSelects = filterPanel.find('select');

		filterSelects.on('change', () => {
			filteringItems();
		});

		dateField.on('change', function(e) {
			filteringItems();
		});

		btnSetDate.on('click', function(e) {
			e.preventDefault();
			filteringItems();
		});

		if (freelanceersField.is(':checked')) {
			freelanceersItems.show();
		} else {
			freelanceersItems.hide();
		}

		freelanceersField.on('change', function(e) {
			if (freelanceersField.is(':checked')) {
				freelanceersItems.show();
			} else {
				freelanceersItems.hide();
			}
		});

		function filteringItems() {
			activeFilters = {};

			activeItems = filterItems;

			filterSelects.each(function() {
				const currSelect = jQuery(this);
				const value = currSelect.val();
				const category = currSelect.data('filter-group');

				if (value) {
					combineFilters(category, value.trim().toLowerCase());
				}
			});

			if (dateField.val() !== '') {
				activeItems = activeItems.filter(function(ind, item) {
					let matched = false;
					const dateText = jQuery(item).find('> .tree_label .as-of-date').text();
					const dateStart = new Date(dateText).getTime();
					const selectedDateText = dateField.val();
					const selectedDate = new Date(selectedDateText).getTime();

					if (dateStart < selectedDate) {
						matched = true;
					}

					return matched;
				});
			}

			jQuery.each(activeFilters, (key, value) => {
				activeItems = activeItems.filter((ind, item) => {
					const elem = jQuery(item).find('> .tree_label .' + key);
					let matched = false;

					if (elem.length) {
						const textArr = elem.text().split(',');

						for (let i = 0; i < textArr.length; i++) {
							if (value.includes('' + textArr[i].trim().toLowerCase())) {
								matched = true;
							}
						}
					}

					return matched;
				});
			});

			filterItems.removeClass(lastClass).addClass(hiddenClass);

			activeItems.each(function() {
				const item = jQuery(this);

				item.removeClass(hiddenClass);
				item.parents('li').removeClass(hiddenClass);
				allCheckbox.prop('checked', true);
			});

			list.find('li:visible').each(function() {
				const item = jQuery(this);

				if (item.find('li:visible').length === 0) {
					item.addClass(lastClass);
				}
			});
		}

		function combineFilters(category, value) {
			if (value !== 'all') {
				if (activeFilters[category]) {
					activeFilters[category].push(value);
				} else {
					activeFilters[category] = [];
					activeFilters[category].push(value);
				}
			}
		}
	});
}