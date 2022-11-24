import 'Plugins/tooltipPlugin';

// tabs init
export default function initTooltip() {
	jQuery('a[title]').hoverTooltip({
		positionTypeX: 'center',
		tooltipStructure: '<div class="hover-tooltip"><div class="tooltip-text"></div></div>'
	});
}
