/* Search plugin */
;(function($) {
	function SearchPlugin(options) {
		this.options = $.extend({
			container: '.items-holder',
			items: '.item',
			searchField: '.search-field',
			searchForm: '.search-form',
			btnSearch: '.btn-search',
			btnClearField: '.btn-clear',
			searchItems: '',
			hiddenClass: 'hidden-item',
			noResultsClass: 'no-results',
			delay: 500
		}, options);

		this.init();
	}

	SearchPlugin.prototype = {
		init: function() {
			if (this.options.holder) {
				this.findElements();
				this.attachEvents();
				this.makeCallback('onInit', this);
			}
		},
		findElements: function() {
			this.win = $(window);
			this.page = $('html, body');
			this.holder = $(this.options.holder);
			this.container = this.holder.find(this.options.container);
			this.items = this.container.find(this.options.items);
			this.searchField = this.holder.find(this.options.searchField);
			this.btnSearch = this.holder.find(this.options.btnSearch);
			this.btnClearField = this.holder.find(this.options.btnClearField);
		},
		attachEvents: function() {
			if (this.btnSearch.length) {
				this.btnSearch.on('click', (e) => {
					e.preventDefault();
					this.searchItems();
				});
			} else {
				this.searchField.on('keyup', () => {
					this.searchItems();

					if (this.searchField.val().trim() !== '') {
						this.holder.addClass('no-empty');
					} else {
						this.holder.addClass('no-empty');
					}
				});
			}

			this.searchField.on('click', () => {
				this.holder.addClass('show-drop');
			});

			$(document).on('click', (e) => {
				const targetNode = $(e.target);

				if (!targetNode.closest(this.holder).length) {
					this.holder.removeClass('show-drop');
				}
			});

			this.btnClearField.on('click', (e) => {
				e.preventDefault();
				this.searchField.val('');
				this.searchItems();
			});
		},
		searchItems: function() {
			let value = this.searchField.val().trim().toLowerCase();

			this.holder.removeClass(this.options.noResultsClass);
			this.items.addClass(this.options.hiddenClass);

			this.activeItems = this.items.filter((ind, item) => {
				let matched = false;
				let text = $(item).find(this.options.searchItems).text().trim().toLowerCase();

				if (value !== '') {
					if (text.indexOf(value) !== -1) {
						matched = true;
					}
				}

				if (value === '') {
					matched = true;
				}

				return matched;
			});

			this.activeItems.removeClass(this.options.hiddenClass);

			if (!this.activeItems.length) {
				this.holder.addClass(this.options.noResultsClass);
			}
		},
		makeCallback: function(name) {
			if (typeof this.options[name] === 'function') {
				let args = Array.prototype.slice.call(arguments);

				args.shift();
				this.options[name].apply(this, args);
			}
		}
	};

	$.fn.searchPlugin = function(opt) {
		return this.each(function() {
			$(this).data('SearchPlugin', new SearchPlugin($.extend(opt, {
				holder: this
			})));
		});
	};
}(jQuery));