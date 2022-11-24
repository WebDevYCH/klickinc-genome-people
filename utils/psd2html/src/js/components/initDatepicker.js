import 'Plugins/datepickerPlugin';

export function currentDate() {
	var today = new Date();
	var dd = String(today.getDate()).padStart(2, '0');
	var mm = String(today.getMonth() + 1).padStart(2, '0'); //January is 0!
	var yyyy = today.getFullYear();

	today = yyyy + '-' + mm + '-' + dd;

	$("#datepicker").attr("value", today);

	$(".set-to-today").click(function(e) {
		e.preventDefault();
		$('#datepicker').datepicker('setDate', today);
	});
}

// datepicker init
export function initdatepicker() {
	jQuery('input.datepicker').uiDatepicker({
		dateFormat: 'yy-mm-dd',
		firstDay: 1,
	});
}
