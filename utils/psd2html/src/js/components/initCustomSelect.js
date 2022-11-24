import Selectr from 'mobius1-selectr'

// customSelect init
export default function initCustomSelect() {
	Object.defineProperty(Selectr.prototype, 'mobileDevice', {
		get() { return false; },
		set() {},
		enumerable: true,
		configurable: true
	});

	new Selectr('#klickster-select', {
		searchable: false,
		defaultSelected: false,
		placeholder: "Find a Klickster"
	});

	new Selectr('#unit-select', {
		searchable: false,
		defaultSelected: false,
		placeholder: "Filter by Business Unit"
	});

	var customSelect = new Selectr('#tabset-nav-select', {
		searchable: false,
		defaultSelected: false,
		renderSelection: myRenderFunction
	});

	const tabsetSelect = jQuery('select.tabset');
	const page = jQuery('html, body');

	jQuery('.tabset-link').on('click', function(e) {
		e.preventDefault();
		const link = jQuery(this);
		const section = jQuery('#' + link.attr('href'));

		if (customSelect && section.length && tabsetSelect.length) {
			customSelect.setValue(link.attr('href'));

			page.animate({
				scrollTop: tabsetSelect.offset().top - 46
			}, 500);
		}
	});

	function myRenderFunction(option) {
		var template = ['<div class="my-template"><div class="ico-holder"><img src="', option.getAttribute('data-src'), '"></div><span>', option.textContent.trim(), '</span></div>'];
		return template.join('');
	}
}
