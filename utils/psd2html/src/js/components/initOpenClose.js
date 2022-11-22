import 'Plugins/openClosePlugin';

// open-close init
export default function initOpenClose() {
	jQuery('.has-open-close').openClose({
		activeClass: 'active',
		opener: '.opener',
		slider: '.slide',
		animSpeed: 400,
		effect: 'slide',
	});

	const activeClass ='active';

	jQuery('.genome-dashboard .content-box').each(function() {
		const holder = jQuery(this);
		const btnExpand = holder.find('.btn-expand');
		const openCloseHolders = holder.find('.has-open-close');

		btnExpand.on('click', function(e) {
			e.preventDefault();

			openCloseHolders.each(function() {
				const openClose = openCloseHolders.data('OpenClose');

				if (btnExpand.hasClass(activeClass)) {
					if (openClose) {
						btnExpand.removeClass(activeClass);
						openClose.hideSlide();
					}
				} else {
					if (openClose) {
						btnExpand.addClass(activeClass);
						openClose.showSlide();
					}
				}
			});
		});
	});
}