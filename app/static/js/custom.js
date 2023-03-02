
function loading(){
    $(".loading").show();      
}
function unloading(){
    $(".loading").hide();
}
function showModalLoading() {
    $(".modal-spinner").removeClass('d-none');
}
function hideModalLoading() {
    $(".modal-spinner").addClass('d-none');
}

document.addEventListener("DOMContentLoaded", () => {
	setActiveSidebarItem();
});

/**
 * Set active sidebar item
 */
function setActiveSidebarItem() {
	let LinkLocation= $('nav a[href^="' + window.location.pathname+ '"]').first();
	LinkLocation.parent('.sidebar-item').addClass('active');
	
	let ul = LinkLocation.closest('ul');
	ul.addClass('show');
	ul.siblings('a').removeClass('collapsed');
	ul.siblings('a').attr('aria-expanded', 'true');
}