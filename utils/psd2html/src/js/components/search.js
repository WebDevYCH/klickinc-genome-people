import 'Plugins/searchPlugin';

export default function initSearch() {
	jQuery('.search-holder').searchPlugin({
		container: '.search-drop ul',
		items: '>li',
		searchField: '[type="text"]',
		searchItems: '.genome-user-name',
		btnClearField: '.btn-clear'
	});
}