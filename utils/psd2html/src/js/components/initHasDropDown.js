// hasDropDown init
export default function initHasDropDown() {
  jQuery('.my-team-list li').each(function() {
		var item = jQuery(this);
		var drop = item.find('.slide');
		var link = item.find('a').eq(0);
		if (drop.length) {
			item.addClass('has-open-close');
			if (link.length) link.addClass('has-open-close-a');
		}
	});
}
