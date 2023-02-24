/* -------------------------------------------------------------------------- */
/*                           Selectors and Variables                          */
/* -------------------------------------------------------------------------- */
const textSearchInput = document.querySelector("#text_search");
const jobTitleSelect = document.querySelector("#job_title_select");
const datePostedSelect = document.querySelector("#date_posted_select");
const createJobBtn = document.querySelector("#create-job-btn");
const clientSearchInput = document.querySelector("#client_search");
const brandsSearchInput = document.querySelector("#brands_search");
const sortBySelect = document.querySelector("#sort_by_select");

var editorContainer; // this.form-editor-container is set in openJobFormModal() for setting classes
var editorInput; // this #quill-editor is set in openJobFormModal() for event listeners

const JOB_MODE = { create: "Create", edit: "Edit" }; // job form mode
var jobFormMode = JOB_MODE.create; // flag to determine if the form is in create or edit mode

/* ----------------------- Set up comboboxes in filter ---------------------- */
const cstFilterCombo = new dhx.Combobox("cst_filter_select", {
    multiselection: true,
    data: csts,
	placeholder: "All CSTs",
	label: "CSTs",
	helpMessage: "Text search for CSTs (allow multiple selections)",
});

const jobFxnFilterCombo = new dhx.Combobox("job_function_select", {
    multiselection: true,
    data: jobfunctions,
	label: "Job Functions",
	helpMessage: "Text search for job function (allow multiple selections)",
	placeholder: "All job functions",
});

/* -------------------------------------------------------------------------- */
/*                               Event Listeners                              */
/* -------------------------------------------------------------------------- */
createJobBtn.addEventListener("click", function () {
	jobFormMode = JOB_MODE.create;
	openJobFormModal(0);
});

jobFxnFilterCombo.events.on("change", function () {
	filterJobList();
});
cstFilterCombo.events.on("change", function () {
	filterJobList();
});

// handle javascript events for filter inputs and selects
function handleFilterEvent(element, event) {
	element.addEventListener(event, function () {
		filterJobList();
	});
}
handleFilterEvent(textSearchInput, "keyup");
handleFilterEvent(brandsSearchInput, "keyup");
handleFilterEvent(clientSearchInput, "keyup");
handleFilterEvent(jobTitleSelect, "change");
handleFilterEvent(datePostedSelect, "change");
handleFilterEvent(sortBySelect, "change");
/* -------------------------------------------------------------------------- */
/*                                  Job List                                  */
/* -------------------------------------------------------------------------- */

function jobListTemplate(job) {
	let expiredOrRemoved = job.removed_date || job.expiry_date < new Date().toISOString().slice(0, 10);
	let status;
	if (expiredOrRemoved) { status = job.removed_date ? "Post closed" : "Post expired"; }

	let template = `
		<div class="accordion-item  job-card mb-2">
			<div class='card-body'> 
				<h2 class="accordion-header" id="job-header-`+ job.id +`">
					<div class="accordion-button d-block collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#job-description-`+ job.id +`" aria-expanded="true" aria-controls="#job-description-`+ job.id +`">
						<div class="d-flex mb-2 justify-content-between align-items-center">
							<div class="d-flex align-items-center">
								<span class="card-title text-primary fs-4 me-1" job-posting-id="` +job.id+ `">` +job.title + `</span>
								`+(job.cst ?`<span class="badge rounded-pill bg-primary me-1">`+ job.cst+`</span> `:'')+`
								`+(job.apply == 1 ?`<span class="badge rounded-pill bg-success">Applied</span>`:'')+`
								<span class="badge rounded-pill bg-primary card-category" hidden category-id="` +job.job_posting_category_id + `">` +job.job_posting_category_name + `</span>
								<span class="badge rounded-pill bg-primary card-similarity" hidden>` +job.similarity + `</span>
								<span claingenomess="card-expiry" hidden>` +job.expiry_date + `</span>
							</div>
							` + (expiredOrRemoved 
								? `<span class="text-muted"><i>`+ status +`</i></span>`  
								: `<span class="text-muted"><i>Posted `+(job.posted_for > 1 ? job.posted_for + ` days ago`: (job.posted_for == 0 ? `today` : `1 day ago` )) +`</i></span>` ) +`
							</div>
						<div class="card-subtitle show-on-collapse text-muted text-truncate">` + job.description.replace(/<[^>]+>/g, '') + `</div>
						<div class="text-muted no-show-on-collapse align-items-center">
							<div>Start Date: `+new Date(job.job_start_date).toISOString().slice(0, 10)+`</div>
							<div>End Date: `+new Date(job.job_end_date).toISOString().slice(0, 10)+`</div>
							<div>Location: `+job.job_location+`</div>
						<div>
						<div class="no-show-on-collapse d-flex align-items-center justify-content-between">
								<div>
									` + (expiredOrRemoved ? '' : `<label class="text-danger">Expires in ` + job.expiry_day + ` days</label>` ) +`
								</div>
								<div>
									` + (current_user_id  == job.poster_user_id ? `					
										<button type="button" class="header-job-btn btn btn-primary view_applicants_btn">View Applicants</button>
										<button type="button" class="header-job-btn btn btn-primary edit-post job_form_btn">Edit Post</button>
										` + (expiredOrRemoved ? '' : `<button type="button" class="header-job-btn btn btn-primary close_post_btn">Close Post</button>` ) +`
									` : '') + `
									`+ (job.apply == 0 && current_user_id  != job.poster_user_id ? `
										<button type="button" class="header-job-btn btn btn-primary apply_job_btn">Apply</button>
									`:'') + `
									`+ (job.apply == 1 ? `
										<button type="button" class="header-job-btn btn btn-primary cancel_application_btn">Cancel Application</button>
									`:'') + `
								</div>
						</div>
					</div>
				</h2>
			</div>
			<div id="job-description-` +  job.id + `" class="accordion-collapse collapse" aria-labelledby="job-header-`+ job.id +`" data-bs-parent="#jobListAccordion">
				<div class="accordion-body">
					<div class="row">
						<div class="col-12">
							<div class="card-description">` +  job.description + `</div>
							<div class="d-flex mb-2 align-items-start justify-content-between">
								<div>
									<div>Start Date: `+new Date(job.job_start_date).toISOString().slice(0, 10)+`</div>
									<div>End Date: `+new Date(job.job_end_date).toISOString().slice(0, 10)+`</div>
									<div>Expected Hours: `+job.expected_hours+`</div>
								</div>
								<div>
									<div>Location: `+job.job_location+`</div>
									<div>CST: `+job.cst+`</div>
									<div>Job Function: `+job.job_function+`</div>
								</div>
								<div>
									<div>Client: `+job.client+`</div>
									<div>Brands: `+job.brands+`</div>
									<div>ProjectID: `+job.project_id+`</div>
									<div>Hiring Manager: `+job.hiring_manager+`</div>
								</div>
								
								
							</div>
							`+ (job.job_posting_skills ?
								`<div class="other-info">
									`+ job.job_posting_skills.join(', ') +`
								</div>`
								:'') 
							+`
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
	eventHandlers: { // event handlers for job list
		onclick: {
			job_form_btn: function(event, id) {
				event.preventDefault(); // prevent dhtmlx scrolling to top
				jobFormMode = JOB_MODE.edit;
				openJobFormModal(id);
			},
			apply_job_btn: function(event, id) {
				event.preventDefault();
				openApplyFormModal(id);
			},
			close_post_btn: function(event, id) {
				event.preventDefault();
				closePostConfirm(id);
			},
			cancel_application_btn: function(event, id) {
				event.preventDefault();
				cancelApplicationConfirm(id);
			},
			view_applicants_btn: function(event, id) {
				event.preventDefault();
				openApplicantsModal(id);
			},
		},
		onmouseover: {
			job_form_btn: function(event) {
				setAccordionCollapse(event, false);
			},
			apply_job_btn: function(event) {
				setAccordionCollapse(event, false);
			},
			close_post_btn: function(event) {
				setAccordionCollapse(event, false);
			},
			cancel_application_btn: function(event) {
				setAccordionCollapse(event, false);
			},
			view_applicants_btn: function(event) {
				setAccordionCollapse(event, false);
			},
		},
		onmouseout: {
			job_form_btn: function(event) {
				setAccordionCollapse(event);
			},
			apply_job_btn: function(event) {
				setAccordionCollapse(event);
			},
			close_post_btn: function(event) {
				setAccordionCollapse(event);
			},
			cancel_application_btn: function(event) {
				setAccordionCollapse(event);
			},
			view_applicants_btn: function(event) {
				setAccordionCollapse(event);
			},
		},
	}
});

jobList.data.parse(jobs);
jobList.data.sort({
    by: "posted_date",
    dir: "desc"
});

/* -------------------------------------------------------------------------- */
/*                         Job Posting Form and Modal                         */
/* -------------------------------------------------------------------------- */
const jobFormConfig = {
	padding: 0,
	css: "job-form",
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
			type: "container",
			css: "form-editor-container dhx_form-group--required",
			html: `
				<label class="dhx_label">Description</label>
				<div class="clearfix editor-container mb-1">
					<div id="quill-toolbar">
						<span class="ql-formats">
							<select class="ql-size"></select>
						</span>
						<span class="ql-formats">
							<select class="ql-color"></select>
						</span>
						<span class="ql-formats">
							<button class="ql-bold"></button>
							<button class="ql-italic"></button>
							<button class="ql-underline"></button>
							<button class="ql-strike"></button>
						</span>
						<span class="ql-formats">
							<button class="ql-header" value="1"></button>
							<button class="ql-header" value="2"></button>
						</span>
						<span class="ql-formats">
							<button class="ql-list" value="ordered"></button>
							<button class="ql-list" value="bullet"></button>
						</span>
					</div>
					<div id="quill-editor" class="dhx_input"></div>
					<span class="dhx_input__caption invalidMsg">Description is required</span>
				</div>
			`
		},
		{
			cols: [
				{
					name: "cst",
					type: "combo",
					label: "CST",
					padding: "0 10px 0 0",
					width: "50%",
					itemHeight: "auto",
					errorMessage: "CST must be selected",
					validation: function(value) {
						return value;
					},
					required: true,
					data: csts
				},
				{
					name: "job_function",
					type: "combo",
					width: "50%",
					label: "Job Function",
					itemHeight: "auto",
					errorMessage: "Job function must be selected",
					validation: function(value) {
						return value;
					},
					required: true,
					data: jobfunctions
				},
			]
		},
		{
			cols: [
				{
					type: "datepicker",
					name: "job_start_date",
					padding: "0 10px 0 0",
					label: "Job Start Date",
					required: true,
					width: "35%",
					errorMessage: "Job start date is required and must not be in the past",
					validation: function(value) {
						return value && new Date(value) >= new Date();
					},
					dateFormat: "%Y-%m-%d",
				},
				{
					type: "datepicker",
					name: "job_end_date",
					label: "Job End Date",
					required: true,
					width: "35%",
					padding: "0 10px 0 0",
					errorMessage: "Job end date is required and must not be after the job start date",
					validation: function(value) {
						return value && new Date(value) >= new Date();
					},
					dateFormat: "%Y-%m-%d",
				},
				{
					type: "datepicker",
					name: "expiry_date",
					label: "Posting Expiry Date",
					width: "30%",
					required: true,
					errorMessage: "Expiry date is required and must not be in the past",
					validation: function(value) {
						return value && new Date(value) >= new Date();
					},
					dateFormat: "%Y-%m-%d",
				},
			]
		},
		{
			cols: [
				{
					name: "job_location",
					type: "input",
					padding: "0 10px 0 0",
					width: "50%",
					label: "Location",
					placeholder: "Job location",
					errorMessage: "Job location is required",
					validation: function(value) {
						return value && value != "";
					},
					required: true,
				},
				{
					name: "expected_hours",
					type: "input",
					label: "Expect Hours",
					inputType: "number",
					width: "50%",
					required: true,
					errorMessage: "Expected hours is required",
					validation: function(value) {
						return value && value != "";
					},
					placeholder: "Total expected hours of work",
				},
			]
		},
		{
			cols: [
				{
					name: "client",
					type: "input",
					padding: "0 10px 0 0",
					width: "50%",
					label: "Client",
					placeholder: "Name of client",
					errorMessage: "Client is required",
					validation: function(value) {
						return value && value != "";
					},
					required: true,
				},
				{
					name: "brands",
					type: "input",
					label: "Brand(s)",
					width: "50%",
					placeholder: "Name of brand(s)",
					errorMessage: "Brands is required",
					validation: function(value) {
						return value && value != "";
					},
					required: true,
				},
			]
		},
		{
			cols: [
				{
					name: "project_id",
					type: "input",
					inputType: "number",
					width: "50%",
					padding: "0 10px 0 0",
					label: "Project ID",
					placeholder: "Project ID",
					errorMessage: "Project is required",
					validation: function(value) {
						return value && value != "" && value > 0;
					},
					required: true,
				},
				{
					name: "hiring_manager",
					type: "input",
					inputType: "number",
					width: "50%",
					label: "Hiring Manager ID",
					placeholder: "Hiring manager ID",
					errorMessage: "Hiring manager is required",
					validation: function(value) {
						return value && value != "";
					},
					required: true,
				}
			]
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
	loading();
	const url = jobFormMode == JOB_MODE.edit ? "/tmkt/editjob" : "/tmkt/postjob";

	var jobData = editForm.getValue();
	jobData.description = editor.root.innerHTML;

	let toastMsg = "Job posting updated successfully";
	let toastType = "success";
	$.ajax({
		type: 'POST',
		url: url,
		data: jobData,
		success: function(data) {
			let parseData = JSON.parse(data);
			if(jobFormMode == JOB_MODE.edit) {
				jobList.data.update(parseData.id, parseData);
			} else {
				jobList.data.add(parseData);
				toastMsg = "Job posting created successfully";
			}
			jobList.data.sort({
				by: "posted_date",
				dir: "desc"
			});
		},
		error: function(err) {
			toastType = "error";
			toastMsg = err.responseJSON?.message || "An error occurred while posting job. Please try again later.";
		},
		complete: function() {
			unloading();
			showToast(toastType, toastMsg);
		}
	});
	closeModal(editForm, editJobFormModal);
});

editForm.getItem("cancel-posting-btn").events.on("click", () => {
	closeModal(editForm, editJobFormModal);
});

// start date and end date date range set up
let startDate = editForm.getItem("job_start_date").getWidget();
let endDate = editForm.getItem("job_end_date").getWidget();
startDate.link(endDate)

// Datepicker does not clear validation on focus automatically so we need to do it manually
function clearDateValidateOnFocus(field) {
	editForm.getItem(field).events.on("focus", () => {
		editForm.getItem(field).clearValidate();
	});
}
// Datepicker does not validate automatically so we need to do it manually
function validateDateOnBlur(field) {
	editForm.getItem(field).events.on("blur", () => {
		editForm.getItem(field).validate();
	});
}

clearDateValidateOnFocus("job_start_date");
clearDateValidateOnFocus("job_end_date");
clearDateValidateOnFocus("expiry_date");
validateDateOnBlur("job_end_date");
validateDateOnBlur("expiry_date");
validateDateOnBlur("job_start_date");

/**
 * check if the description is valid and add or remove the error class manually 
 * (because the dhtmlx Form does not support Quill editor)
 * @returns {boolean} true if the description is valid, false otherwise
 */
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

const editJobFormModal = new dhx.Window({
	width: getWindowSize().width,
	height: getWindowSize(960).height,
	title: "Edit Job Posting",
	modal: true
});

let isEditorInitialized = false; //editor can be initialized only once
let editor; // quill editor

/**
 * open the editing form, clear the form, and fill the form fields with the data of the item (if the item is not null) 
 * initialize the editor if it is not initialized yet (only once between url refresh)
 * @param id the id of the item to be edited or 0 if the item is new
 */
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
			theme: "snow",
			scrollingContainer: ".dhx_form"
		});
		editorContainer = document.querySelector(".form-editor-container");
		editorInput = document.querySelector("#quill-editor");
		editorInput.addEventListener("focusout", function (e) {
			isValidDescription();
		});
	}

	const item = jobList.data.getItem(id);
	editJobFormModal.header.data.update("title", { value: jobFormMode + " Job Posting" } );
	editForm.clear(); // clear the form data from cache
	if (item) {
		editor.root.innerHTML = item.description;
		editForm.setValue(item);
		// Clear validation messages when clicking between items
		editForm.clear("validation");
	}else{
		editor.root.innerHTML = "";
	}

	// manually remove classes on load
	editorContainer.classList.remove("dhx_form-group--state_error");
	editorContainer.classList.remove("dhx_form-group--state_success");
}

// attaching Form to Window
editJobFormModal.attach(editForm);

// close/delete job posting on .close_post_btn click
function closePostConfirm(id) {
	const item = jobList.data.getItem(id);
	dhx.confirm({
		header: "Close Job Posting",
		text: "Are you sure you want to close this job posting for " + item.title + "?",
		buttons: ["Cancel", "Proceed"],
	}).then(function (res) {
		 if (res) {
			loading();
			$.ajax({
				url: "/tmkt/closepost",
				method: "POST",
				data: {id: id},
				success: function(data) {
					let parseData = JSON.parse(data);
					jobList.data.update(parseData.id, parseData);
					unloading();
					showToast("success", "Job posting closed successfully.");
				},
				error: function(err) {
					unloading();
					showToast("error", err.responseJSON?.message || "An error occurred while closing job posting.");
				}
			})
		 } 
	});
}

// cancel job application on .cancel_application_btn click
function cancelApplicationConfirm(id) {
	const item = jobList.data.getItem(id);
	dhx.confirm({
		header: "Cancel Job Application",
		text: "Are you sure you want to cancel this job application for " + item.title + "?",
		buttons: ["Cancel", "Proceed"],
	}).then(function (proceed) {
		 if (proceed) {
			loading();
			$.ajax({
				url: "/tmkt/cancelapplication",
				method: "POST",
				data: {id: id},
				success: function() {
					jobList.data.update(id, {apply: 0});
					if(window.location.pathname.includes("/jobsearch/applied")) {
						jobList.data.remove(id);
					}
					unloading();
					showToast("success", "Application cancelled successfully!");
				},
				error: function(err) {
					unloading();
					showToast("error", err.responseJSON?.message || "An error occurred while cancelling the application.");
				}
			})
		 } 
	});
}
/* -------------------------------------------------------------------------- */
/*                                Apply for Job                               */
/* -------------------------------------------------------------------------- */
function openApplyFormModal(id) {
	applyForm.clear();
	const item = jobList.data.getItem(id);

	if (item) {
		applyJobFormModal.header.data.update("title", { value: "Application for " + item.title } );
		applyForm.setValue(item);
	}
	applyJobFormModal.show();
}

const applyJobFormModal = new dhx.Window({
	width: getWindowSize().width,
	height: getWindowSize(600).height,
	title: "Apply",
	modal: true
});

const applyFormConfig = {
	padding: 0,
	rows: [
		{
			type: "input",
			name: "id",
			hidden: true
		},
		{
			type: "container", //container for HTML code
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
			errorMessage: "Brief description is required",
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
			errorMessage: "Skills or experience are required",
			validation: function(value) {
				return value && value != "";
			},
		},
		{
            name: "worked_with_brand",
            type: "radioGroup",
			labelPosition: "left",
            required: true,
            label: "Have you worked with this brand before?",
			errorMessage: "Please select an option",
			validation: function(value) {
				return value && value != "";
			},
            options: {
                rows: [
                    {
                        type: "radioButton",
                        text: "Yes, at Klick or Katalyst",
                        value: "Yes, at Klick or Katalyst",
                    },
                    {
                        type: "radioButton",
                        text: "Yes, before joining Klick",
                        value: "Yes, before joining Klick"
                    },
					{
                        type: "radioButton",
                        text: "No",
                        value: "No"
                    },
                ]
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
					css: "me-1"
				},
				{
					id: "submit-apply-btn",
					type: "button",
					text: "Apply",              
					size: "medium",
					color: "primary",
				}
			]
		}
		
	]
}

const applyForm = new dhx.Form(null, applyFormConfig);

// on apply button submit click
// validate form and send data to server
applyForm.getItem("submit-apply-btn").events.on("click", function () {
	if(!applyForm.validate()) return;
	
	var data = applyForm.getValue();
	loading();
	$.ajax({
		url: "/tmkt/applyjob",
		method: "POST",
		data: data,
		success: function() {
			jobList.data.update(data.id, {apply: 1});
			unloading();
			showAlert("Your Application Has Been Submitted", "You can review all submitted applications and their status in the 'Applied Jobs' section of Job Board.");
		},
		error: function(err) {
			unloading();
			showToast("Error", err.responseJSON?.message || "An error occurred while submitting your application. Please try again later.");
		}
	});
	closeModal(applyForm, applyJobFormModal);
});

applyForm.getItem("cancel-apply-btn").events.on("click", () => {
	closeModal(applyForm, applyJobFormModal);
});

applyJobFormModal.attach(applyForm);


/* -------------------------------------------------------------------------- */
/*                             View Job Applicants                            */
/* -------------------------------------------------------------------------- */
function viewApplicantTemplate(applicant){
	if(applicant.title == "No applicants yet") return `<div class="row px-2">` + applicant.title + `</div>`;
	let template = `
		<div class="row">
			<div class="d-flex align-items-center justify-content-between">
				<div>
					<span class="card-title mb-0 text-primary">`+applicant.firstname+` `+applicant.lastname+`</span>
					<div>`+applicant.cst+` `+applicant.title+`</div>
				</div>
				<div>
					<div class="d-flex justify-content-end">`+applicant.applied_date+`</div>
					<a href="#" class="d-flex justify-content-end"">View profile</a>
					<a href="#" class="d-flex justify-content-end">Request approval</a>
				</div>
			</div>
		</div>
	`;
	return template;
}

const applicantList = new dhx.List(null, {
	css:"dhx_widget--bg_white applicant-ul-list",
	template: viewApplicantTemplate,
});


// on click of view applicants button
// get applicants (or no data) for the job posting
// and display in modal
function openApplicantsModal(id) {
	// viewApplicantsModal.show();
	// applicantList.data.parse(applicants);
	applicantList.data.parse([]); //clear data from previous view
	$.ajax({
		url: "/tmkt/getapplicants",
		method: "POST",
		data: {
			job_posting_id: id
		},
		success: function(data) {
			if(data && data.length > 0) {
				applicantList.data.parse(data);
			}else{
				applicantList.data.add({ title: "No applicants yet"});
			}
			viewApplicantsModal.show();
		}
	}); 
}

const viewApplicantsModal = new dhx.Window({
	width: getWindowSize().width,
	height: getWindowSize(540).height,
	title: "View Applicants",
	modal: true
});

viewApplicantsModal.attach(applicantList);

/* -------------------------------------------------------------------------- */
/*                              Helper Functions                              */
/* -------------------------------------------------------------------------- */

// initializing the function that closes the form and clears it
function closeModal(form, modal) {
	form.clear();
	modal.hide();
}


/**
 * return the window/modal size based on the screen size
 * @param {number} baseHeight the height of the modal including the header
 * @returns {object} returns an object with the width and height of the modal
 */
function getWindowSize(baseHeight = 0) {
	let width;
	let height;
	if (window.innerWidth < 768) { //on mobile
		width = window.innerWidth;
	} else if (window.innerWidth < 992) {
		width = 798;
	} else {
		width = 900;
	} 

	if(window.innerHeight < baseHeight || window.innerWidth < 768){ //on mobile
		height = window.innerHeight;
	}else{
		height = baseHeight;
	}
	return { width: width , height: height };
}

/**
 * Prevent accordion from collapsing when clicking on the button
 * By setting the data-bs-toggle attribute to "collapse" or removing it
 * @param {event} event  the mouse over event.
 * @param {boolean} collapse  true if accordion should collapse, false if not.
 */
function setAccordionCollapse(event, collapse = true) {
	let accordionButton = event.target.closest('.accordion-button');
	if (accordionButton && collapse) accordionButton.setAttribute('data-bs-toggle', "collapse");
	else if (accordionButton && !collapse) accordionButton.removeAttribute('data-bs-toggle');
}

/**
 * show window popup with alert message
 * @param {string} header the header title of the alert
 * @param {string} text the description of the alert
 */
function showAlert(header, text) {
	dhx.alert({
		header: header,
		text: text,
		buttonsAlignment: "center",
		buttons: ["ok"],
	});
}


/* -------------------------------------------------------------------------- */
/*                              Filter Functions                              */
/* -------------------------------------------------------------------------- */

// Filter by text search for title and description
// Filter by select for title, category and date posted
function filterJobList() {
	const title = jobTitleSelect.value.toLowerCase();
	const text = textSearchInput.value.toLowerCase();
	const datePosted = datePostedSelect.value;
	const jobFunction = jobFxnFilterCombo.getValue();
	const cst = cstFilterCombo.getValue();
	const client = clientSearchInput.value.toLowerCase();
	const brand = brandsSearchInput.value.toLowerCase();
	const sortBy = sortBySelect.value;

	const today = new Date();
	let filteredList = jobs.filter(function(item) {
		
		const timeDiff = today.getTime() - new Date(item.posted_date).getTime();
		const diffDays = Math.ceil(timeDiff / (1000 * 3600 * 24));
		
		// TODO: update client and brand filter because there is no null record on prod
		return (
			(item.title.toLowerCase().includes(text) || item.description.toLowerCase().includes(text)) &&
			(item.title.toLowerCase().includes(title)) &&
			(diffDays <= datePosted || datePosted == 0) &&
			(jobFunction.includes(item.job_function) || jobFunction.length == 0) &&
			(cst.includes(item.cst) || cst.length == 0) &&
			(item.client?.toLowerCase().includes(client) || client == "") &&
			(item.brands?.toLowerCase().includes(brand) || brand == "")
		);
	});

	jobList.data.parse(filteredList);

	// TODO: update sort by with skills match once skills are added
	let sortByField = "posted_date";
	let sortDir = "desc";
	if(sortBy == "least recent"){
		sortByField = "posted_date";
		sortDir = "asc";
	}else if(sortBy == "start date"){
		jobList.data.sort({
			rule: function (a, b) {
				return new Date(a.job_start_date) - new Date(b.job_start_date);
			}
		});
	}

	if(sortBy != "start date"){
		jobList.data.sort({
			by: sortByField,
			dir: sortDir
		});
	}
}
