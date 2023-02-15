
/* -------------------------------------------------------------------------- */
/*                           Selectors and Variables                          */
/* -------------------------------------------------------------------------- */
const textSearchInput = document.querySelector("#text_search");
const jobTitleSelect = document.querySelector("#job-title-select");
const datePostedSelect = document.querySelector("#date-posted-select");
const createJobBtn = document.querySelector("#create-job-btn");

var editorContainer; // this.form-editor-container is set in openJobFormModal() for setting classes
var editorInput; // this #quill-editor is set in openJobFormModal() for event listeners

var jobFormMode = "Create"; // flag to determine if the form is in create or edit mode


/* -------------------------------------------------------------------------- */
/*                               Event Listeners                              */
/* -------------------------------------------------------------------------- */
createJobBtn.addEventListener("click", function () {
	jobFormMode = "Create";
	openJobFormModal(0);
});
textSearchInput.addEventListener("keyup", function () {
	filterJobList();
});
jobTitleSelect.addEventListener("change", function () {
	filterJobList();
});
datePostedSelect.addEventListener("change", function () {
	filterJobList();
});


/* -------------------------------------------------------------------------- */
/*                                  Job List                                  */
/* -------------------------------------------------------------------------- */
function jobListTemplate(job) {
	let template = `
		<div class="accordion-item  job-card mb-2">
			<div class='card-body'> 
				<h2 class="accordion-header" id="job-header-`+ job.id +`">
					<div class="accordion-button d-block collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#job-description-`+ job.id +`" aria-expanded="true" aria-controls="#tmkt`+ job.id +`">
						<div class="d-flex mb-2 justify-content-between align-items-center">
							<div class="d-flex align-items-center">
								<span class="card-title text-primary fs-3 me-1" job-posting-id="` +job.id+ `">` +job.title + `</span>
								<span class="badge rounded-pill bg-primary card-category" category-id="` +job.job_posting_category_id + `">` +job.job_posting_category_name + `</span>
								<span class="badge rounded-pill bg-primary card-similarity" hidden>` +job.similarity + `</span>
								<span class="card-expiry" hidden>` +job.expiry_date + `</span>
							</div>
							<span class="text-muted"><i>`+(job.posted_for > 1 ? job.posted_for + ` Days Ago`: (job.posted_for == 0 ? `Today` : `1 Day Ago` )) +`</i></span>
						</div>
						<div class="card-subtitle text-muted text-truncate">` + job.description.replace(/<[^>]+>/g, '') + `</div>
					</div>
				</h2>
			</div>
			<div id="job-description-` +  job.id + `" class="accordion-collapse collapse" aria-labelledby="job-header-`+ job.id +`" data-bs-parent="#jobListAccordion">
				<div class="accordion-body">
					<div class="row">
						<div class="col-md-10">
							<div class="card-description">` +  job.description + `</div>
							<div class="other-info">
								`+ job.job_posting_skills.join(', ') +`
							</div>
						</div>
						<div class="col-md-2">
							<div class="clearfix">
								`+(job.apply == 1 ?`<span class="text-success float-end">Applied</span>`:'')+`
							</div>
							<div class="clearfix">
								<label class="float-end text-danger">Expires in ` + job.expiry_day + ` days</label>
							</div>
							` + (current_user_id  == job.poster_user_id ? `
							<div class="clearfix">
								<a href="#" class="float-end text-decoration-underline">View applicants</a>
							</div>
							<div class="clearfix">
								<a href="#" class="float-end text-decoration-underline edit-post job_form_btn">Edit post</a>
							</div>
							<div class="clearfix">
								<a href="#" class="float-end text-decoration-underline" data-bs-toggle="modal" data-bs-target="#close_post_modal">Close post</a>
							</div>` : '') + `
							`+ (job.apply == 0 && current_user_id  != job.poster_user_id ? `
								<div class="clearfix">
									<a href="#" class="float-end text-decoration-underline apply_job_btn">Apply</a>
								</div>
							`:'') + `
							`+ (job.apply == 1 ? `
							<div class="clearfix">
								<a href="#" class="float-end text-decoration-underline" data-bs-toggle="modal" data-bs-target="#cancel_application_modal">Cancel application</a>
							</div>
							`:'') + `
						</div>
					</div>
				</div>
			</div>
		</div>
	`;
	return template;
}

const jobList = new dhx.List("jobListView", {
	css: "dhx_widget--bg_gray job-ul-list",
	template: jobListTemplate,
	eventHandlers: { //adds event handlers to HTML elements of a custom template
		onclick: {
			job_form_btn: function(event, id) {
				jobFormMode = "Edit";
				openJobFormModal(id);
			},
			apply_job_btn: function(event, id) {
				openApplyFormModal(id);
			},
		},
	}
});

jobList.data.parse(jobs);


/* -------------------------------------------------------------------------- */
/*                              Job Posting Form                              */
/* -------------------------------------------------------------------------- */
const jobFormConfig = {
	padding: 0,
	rows: [
		{
			id: "id",
			type: "input",
			name: "id",
			hidden: true
		},
		{
			name: "title",
			type: "select",
			label: "Title",
			required: true,
			labelPosition: "top",
			errorMessage: "Job title must be selected",
			validation: function(value) {
				return value && value != "0";
			},
			options: titles
		},
		{
			name: "job_posting_category_id",
			type: "select",
			label: "Category",
			labelPosition: "top",
			errorMessage: "Job category must be selected",
			validation: function(value) {
				return value && value != "0";
			},
			required: true,
			options: categories
		},
		{
			type: "datepicker",
			name: "expiry_date",
			label: "Expiry Date",
			required: true,
			errorMessage: "Expiry date is required and must not be in the past",
			validation: function(value) {
				return value && new Date(value) >= new Date();
			},
			dateFormat: "%Y-%m-%d",
		},
		{
			type: "container", //container for HTML code
			css: "form-editor-container dhx_form-group--required",
			html: `
				<label class="dhx_label">Description</label>
				<div class="clearfix mb-3">
					<div id="quill-toolbar">
						<span class="ql-formats">
							<select class="ql-font"></select>
							<select class="ql-size"></select>
						</span>
						<span class="ql-formats">
							<button class="ql-bold"></button>
							<button class="ql-italic"></button>
							<button class="ql-underline"></button>
							<button class="ql-strike"></button>
						</span>
						<span class="ql-formats">
							<select class="ql-color"></select>
							<select class="ql-background"></select>
						</span>
						<span class="ql-formats">
							<button class="ql-script" value="sub"></button>
							<button class="ql-script" value="super"></button>
						</span>
						<span class="ql-formats">
							<button class="ql-header" value="1"></button>
							<button class="ql-header" value="2"></button>
							<button class="ql-blockquote"></button>
							<button class="ql-code-block"></button>
						</span>
						<span class="ql-formats">
							<button class="ql-list" value="ordered"></button>
							<button class="ql-list" value="bullet"></button>
							<button class="ql-indent" value="-1"></button>
							<button class="ql-indent" value="+1"></button>
						</span>
						<span class="ql-formats">
							<button class="ql-direction" value="rtl"></button>
							<select class="ql-align"></select>
						</span>
						<span class="ql-formats">
							<button class="ql-link"></button>
							<button class="ql-image"></button>
							<button class="ql-video"></button>
						</span>
						<span class="ql-formats">
							<button class="ql-clean"></button>
						</span>
					</div>
					<div id="quill-editor" class="dhx_input"></div>
					<span class="dhx_input__caption invalidMsg">Description is required</span>
				</div>
			`
		},
		{
			align: "end",
			css: "form-btns-container",
			cols: [
				{
					id: "cancel-posting-btn",
					type: "button",
					text: "Cancel",
					view: "link",
					size: "medium",
					color: "primary",
				},
				{
					id: "submit-posting-btn",
					type: "button",
					text: "Submit",              
					size: "medium",
					color: "primary",
					submit: true,
				}
			]
		}
		
	]
}

// initializing Form for the editing form
const editForm = new dhx.Form(null, jobFormConfig);

// assign a handler to the Click event of the button with the id="submit-posting-btn"
// pressing the Submit button will get all data of the form, update data of the edited item, and close the editing form
editForm.getItem("submit-posting-btn").events.on("click", function () {

	if(!(isValidDescription() && editForm.validate())) return;

	const url = jobFormMode == "Edit" ? "/tmkt/editjob" : "/tmkt/postjob";
	
	var jobData = editForm.getValue();
	jobData.description = editor.root.innerHTML;

	$.ajax({
		type: 'POST',
		url: url,
		data: jobData,
		success: function() {
			loading();
			window.location.href = '/tmkt/jobsearch';
		}
	});
	unloading();
	closeModal(editForm, editJobFormModal);
});
// Datepicker does not clear validation on focus automatically so we need to do it manually
editForm.getItem("expiry_date").events.on("focus", () => {
	editForm.getItem("expiry_date").clearValidate();
});
// Datepicker does not validate automatically so we need to do it manually
editForm.getItem("expiry_date").events.on("blur", () => {
	editForm.getItem("expiry_date").validate();
});
editForm.getItem("cancel-posting-btn").events.on("click", () => {
	closeModal(editForm, editJobFormModal);
});

// check if the description is valid and add or remove the error class manually 
// (because the dhtmlx Form does not support Quill editor)
function isValidDescription() {
	if(editor.root.innerHTML == "" || editor.root.innerHTML == "<p><br></p>"){
		editorContainer.classList.add("dhx_form-group--state_error");
		editorContainer.classList.remove("dhx_form-group--state_success");
		return false;
	}else{
		editorContainer.classList.remove("dhx_form-group--state_error");
		editorContainer.classList.add("dhx_form-group--state_success");
		return true;
	}
}

/* -------------------------------------------------------------------------- */
/*                        Modal Window For Editing Form                       */
/* -------------------------------------------------------------------------- */

const editJobFormModal = new dhx.Window({
	width: getWindowSize().width,
	height: getWindowSize(80).height,
	title: "Edit Job Posting",
	modal: true
});

let isEditorInitialized = false; //editor can be initialized only once
let editor; // quill editor

// initializing the function that opens the editing form 
// and fills the form fields with the data of the item
function openJobFormModal(id) {
	editJobFormModal.show();

	// Initialize editor once and set up event listeners
	if(!isEditorInitialized) {
		isEditorInitialized = true;
		editor = new Quill("#quill-editor", {
			modules: {
				toolbar: "#quill-toolbar"
			},
			placeholder: "Write job description here...",
			theme: "snow"
		});
		editorContainer = document.querySelector(".form-editor-container");
		editorInput = document.querySelector("#quill-editor");
		editorInput.addEventListener("focusout", function (e) {
			isValidDescription();
		});
	}

	const item = jobList.data.getItem(id);
	editJobFormModal.header.data.update("title", { value: jobFormMode + " Job Posting" } );
	if (item) {
		editor.root.innerHTML = item.description;
		editForm.setValue(item);
		// Clear validation messages when clicking between items
		editForm.getItem("title").clearValidate();
		editForm.getItem("job_posting_category_id").clearValidate();
		editForm.getItem("expiry_date").clearValidate();
	}else{
		editor.root.innerHTML = "";
		editForm.clear();
	}
	editorContainer.classList.remove("dhx_form-group--state_error");
	editorContainer.classList.remove("dhx_form-group--state_success");
}

// initializing the function that closes the editing form and clears it
function closeModal(form, modal) {
	form.clear();
	modal.hide();
}

// return the window/modal size based on the screen size
function getWindowSize(adjustHeight = 0) {
	if (window.innerWidth < 768) {
		return { width: window.innerWidth, height: window.innerHeight };
	} else if (window.innerWidth < 992) {
		return { width: 798, height: window.innerHeight - adjustHeight };
	} else {
		return { width: 900 , height: window.innerHeight - adjustHeight };
	} 
}

// attaching Form to Window
editJobFormModal.attach(editForm);

/* -------------------------------------------------------------------------- */
/*                                Apply for Job                               */
/* -------------------------------------------------------------------------- */
function openApplyFormModal(id) {
	applyJobFormModal.show();
	const item = jobList.data.getItem(id);
	if (item) {
		applyJobFormModal.header.data.update("title", { value: "Apply for " + item.title } );
	}
	applyForm.clear();
}

const applyJobFormModal = new dhx.Window({
	width: getWindowSize().width,
	height: getWindowSize(400).height,
	title: "Apply",
	modal: true
});

const applyFormConfig = {
	padding: 0,
	rows: [
		{
			id: "id",
			type: "input",
			name: "id",
			hidden: true
		},
		{
			type: "container", //container for HTML code
			css: "",
			html: `
				<div>
					<p>Your profile will be sent to the job poster in addition to the information you provide below.</p>
				</div>
			`
		},
		{
			name: "comments",
			type: "textarea",
			label: "Provide a brief description of why you are a goof match for this job. Feel free to include any information you feel is relevant to your application.",
			required: true,
			labelPosition: "top",
			height: "150px",
			errorMessage: "Comments are required",
			validation: function(value) {
				return value && value != "";
			},
		},
		{
			name: "skills",
			type: "textarea",
			height: "150px",
			label: "Do you have the required skills or experience outlined in the job posting? This can include work outside of Klick",
			required: true,
			labelPosition: "top",
			errorMessage: "Comments are required",
			validation: function(value) {
				return value && value != "";
			},
		},
		{
			align: "end",
			css: "form-btns-container",
			cols: [
				{
					id: "cancel-apply-btn",
					type: "button",
					text: "Cancel",
					view: "link",
					size: "medium",
					color: "primary",
				},
				{
					id: "submit-apply-btn",
					type: "button",
					text: "Submit",              
					size: "medium",
					color: "primary",
					submit: true,
				}
			]
		}
		
	]
}

const applyForm = new dhx.Form(null, applyFormConfig);

applyForm.getItem("submit-apply-btn").events.on("click", function () {
	
	if(!applyForm.validate()) return;
	
	var data = applyForm.getValue();
	loading();
	$.ajax({
		url: "/tmkt/applyjob",
		method: "POST",
		data: data,
		success: function(response) {
			window.location.href = '/tmkt/jobsearch';
		}
	});
	unloading();
	closeModal(applyForm, applyJobFormModal);
});

applyForm.getItem("cancel-apply-btn").events.on("click", () => {
	closeModal(applyForm, applyJobFormModal);
});

applyJobFormModal.attach(applyForm);

/* -------------------------------------------------------------------------- */
/*                              Filter Functions                              */
/* -------------------------------------------------------------------------- */

// Filter by text search for title and description
// Filter by select for title, category and date posted
function filterJobList() {
	const title = jobTitleSelect.value.toLowerCase();
	const text = textSearchInput.value.toLowerCase();
	const datePosted = datePostedSelect.value;

	let filteredList = jobs.filter(function(item) {
		const today = new Date();
		const timeDiff = today.getTime() - new Date(item.posted_date).getTime();
		const diffDays = Math.ceil(timeDiff / (1000 * 3600 * 24));

		return (
			(item.title.toLowerCase().includes(text) || item.description.toLowerCase().includes(text)) &&
			(item.title.toLowerCase().includes(title)) &&
			(diffDays <= datePosted || datePosted == 0)
		);
	});
	
	jobList.data.parse(filteredList);
}


