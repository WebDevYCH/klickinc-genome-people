const TOAST_TYPES = { success: "Success", info: "Notice", warning: "Warning", error: "Error" }; 

/**
 * show toast notification at the top right of the screen
 * @param {string} type the type of toast to show. Can be one of the following: success, info, warning, error
 * @param {string} message the message to display in the toast
 * @param {string} header the header of the toast. If not provided, the header will be the type of toast. Default is null
 * @param {boolean} autohide whether the toast should autohide after 10 seconds. Default is true
 */
function showToast(type, message, header = null, autohide = true){
	const toastContainer = document.getElementById("genome-toast-container");
	const toast = document.createElement("div");
	toast.className = `toast top-0 end-0 ${type.toLowerCase()}`;
	toast.setAttribute("role", "alert");
	toast.setAttribute("aria-live", "assertive");
	toast.setAttribute("aria-atomic", "true");
	
	if(!autohide){
		toast.setAttribute("data-bs-autohide", "false");
	}else{
		toast.setAttribute("data-bs-delay", "10000");
	}
	toast.innerHTML = `
		<div class="d-flex">
			<div class="toast-body">
				<div class="genome-toast-header">${header? header : TOAST_TYPES[type.toLowerCase()]}</div>
				<div>${message}</div>
			</div>
			<button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
		</div>
	`;
	toastContainer.appendChild(toast);
	const toastInstance = new bootstrap.Toast(toast);
	toastInstance.show();
}