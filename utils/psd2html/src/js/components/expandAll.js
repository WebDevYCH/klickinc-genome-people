export default function initExpandAll() {
	const activeClass = 'active';

	jQuery('.genome-main-content .inner-content').each(function() {
		const holder = jQuery(this);
		const btnExpandAll = holder.find('.btn-expand');
		const expandItems = holder.find('.users-tree-menu ul :checkbox');

		btnExpandAll.on('click', function(e) {
			e.preventDefault();

			if (btnExpandAll.hasClass(activeClass)) {
				btnExpandAll.removeClass(activeClass);
				expandItems.prop('checked', false);
			} else {
				btnExpandAll.addClass(activeClass);
				expandItems.prop('checked', true);
			}
		});
	});
}