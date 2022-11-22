// tabs init
export default function initTabs() {
	const tabsetSelect = jQuery('select.tabset');
	const animDuration = 0;

	tabsetSelect.each(function() {
		const select = jQuery(this);
		const selectOptions = select.find('option');
		let activeTab;
		let isAnimating = false;

		selectOptions.each(function() {
			const currentOption = jQuery(this);
			const selectedOptionValue = currentOption.val();
			const currentTab = jQuery('#' + selectedOptionValue);

			if (currentOption.is(':selected')) {
				currentTab.show();
				activeTab = currentTab;
			} else {
				currentTab.hide();
			}
		});

		select.on('change', function() {
			const newTab = jQuery('#' + jQuery(this).val());

			if (!isAnimating) {
				isAnimating = true;
				activeTab.fadeOut(animDuration, function() {
					newTab.fadeIn(animDuration, function() {
						isAnimating = false;
					});
				});

				activeTab = newTab;
			}
		});
	});
}