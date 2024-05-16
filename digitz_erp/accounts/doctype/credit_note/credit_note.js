// Copyright (c) 2023, Rupesh P and contributors
// For license information, please see license.txt

frappe.ui.form.on("Credit Note", {
	onload(frm) {
    	frm.trigger("assign_defaults");
	},
	refresh(frm){
		create_custom_buttons(frm)
		update_total_big_display(frm);
	},
	setup:function(frm)
	{
		frm.set_query('account', 'credit_note_details', () => {
			return {
			  filters: {
				root_type: ['in', ['Expense','Income','Liability','Asset']],
				is_group: 0
			  }
			}
		  });

			  frm.set_query("warehouse", function() {
				  return {
					  "filters": {
						  "disabled": 0
					  }
				  };
			  });

		  frm.set_query('receivable_account', () => {
				  return {
					  filters: {
					  root_type: ['in',  ['Liability','Asset']],
					  is_group: 0
					  }
				  }
				  });

		frm.add_fetch('customer', 'full_address', 'address')
		frm.add_fetch('customer', 'tax_id', 'tax_id')
		frm.add_fetch('customer', 'credit_days', 'credit_days')
		frm.add_fetch('payment_mode', 'account', 'payment_account')

	},

	assign_defaults: function(frm){

		if(frm.is_new())
		{
			default_company = "";

			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					'doctype': 'Global Settings',
					'fieldname': 'default_company'
				},
				callback: (r) => {

					default_company = r.message.default_company
					frm.set_value('company',default_company);

				frappe.db.get_value("Company", default_company, "default_receivable_account").then((r) => {

					frm.set_value('receivable_account',r.message.default_receivable_account);
				});
				}
			});

			frappe.db.get_value('Company', frm.doc.company, 'default_credit_sale', function(r) {
				if (r && r.default_credit_sale === 1) {
						frm.set_value('on_credit', 1);
				}
			});

			set_default_payment_mode(frm);

			frm.clear_table("credit_note_details");
		}
	},

    edit_posting_date_and_time(frm) {
    if (frm.doc.edit_posting_date_and_time == 1) {
      frm.set_df_property("posting_date", "read_only", 0);
      frm.set_df_property("posting_time", "read_only", 0);
    }
    else {
      frm.set_df_property("posting_date", "read_only", 1);
      frm.set_df_property("posting_time", "read_only", 1);
    }
  },

  on_credit(frm) {
		set_default_payment_mode(frm);
		fill_receipt_schedule(frm)

	},
  customer(frm){

	frappe.call(
		{
			method: 'digitz_erp.accounts.doctype.gl_posting.gl_posting.get_party_balance',
			args: {
				'party_type': 'Customer',
				'party': frm.doc.customer
			},
			callback: (r) => {
				frm.set_value('customer_balance',r.message)
				frm.refresh_field("customer_balance");
			}
		});

  },
	rate_includes_tax: function(frm) {
    frappe.confirm('Are you sure you want to change this setting which will change the tax calculation?', () => {
      frm.trigger("make_taxes_and_totals");
    })
	},
	make_taxes_and_totals: function(frm) {
		var total_amount = 0;
		var tax_total = 0;
		var grand_total = 0;
		frm.doc.total_amount = 0;
		frm.doc.tax_total = 0;
		frm.doc.grand_total = 0;

		frm.doc.credit_note_details.forEach(function (entry) {

			var tax_in_rate = 0;
			var amount_excluded_tax = entry.amount;
			var tax_amount = 0;
			var total = 0;

			if(!entry.tax_excluded && entry.tax_rate >0)
			{
				entry.rate_includes_tax = frm.doc.rate_includes_tax;

				if (entry.rate_includes_tax)
				{
          			tax_in_rate = entry.amount * (entry.tax_rate / (100 + entry.tax_rate));
					amount_excluded_tax = entry.amount - tax_in_rate;
					tax_amount = entry.amount * (entry.tax_rate / (100 + entry.tax_rate))
				}
				else {
					amount_excluded_tax = entry.amount;
					tax_amount = (entry.amount * (entry.tax_rate / 100))
				}
			}

			total = amount_excluded_tax + tax_amount;
			frappe.model.set_value(entry.doctype, entry.name, "amount_excluded_tax", amount_excluded_tax);
			frappe.model.set_value(entry.doctype, entry.name, "tax_amount", tax_amount);
			frappe.model.set_value(entry.doctype, entry.name, "total", total);
			total_amount  = grand_total+entry.amount;
			tax_total = tax_total + entry.tax_amount;
			grand_total  = grand_total+entry.total;
		});

		frm.set_value('total_amount', total_amount);
		frm.set_value('tax_total', tax_total);
		frm.set_value('grand_total', grand_total);
		frm.refresh_fields();
		update_total_big_display(frm);
	},

  validate: function (frm) {

		if(!frm.doc.on_credit && !frm.doc.payment_mode)
		{
			frappe.throw("Select payment mode.")
		}

		if(!frm.doc.on_credit && !frm.doc.payment_account)
		{
			frm.refresh_field("payment_account");
			frappe.throw("Select payment account.")
		}
	},
});

function fill_receipt_schedule(frm, refresh=false,refresh_credit_days=false)
{

	if(refresh)
	{
		frm.doc.receipt_schedule = [];
		refresh_field("receipt_schedule");
	}

	console.log("fill_receipt_schedule")

	if (frm.doc.on_credit) {


		var postingDate = frm.doc.posting_date;
		var creditDays = frm.doc.credit_days;
		var roundedTotal = frm.doc.grand_total;

		if (!frm.doc.receipt_schedule) {
			frm.doc.receipt_schedule = [];
		}

		var receiptRow = null;

		row_count = 0;
		// Check if a Payment Schedule row already exists
		frm.doc.receipt_schedule.forEach(function(row) {
			if (row){
				receiptRow = row;
				if(refresh || refresh_credit_days)
				{
					receiptRow.date = creditDays ? frappe.datetime.add_days(postingDate, creditDays) : postingDate;
				}

				row_count++;
			}
		});

		//If there is no row exits create one with the relevant values
		if (!receiptRow) {
			// Calculate receipt schedule and add a new row
			receiptRow = frappe.model.add_child(frm.doc, "Receipt Schedule", "receipt_schedule");
			receiptRow.date = creditDays ? frappe.datetime.add_days(postingDate, creditDays) : postingDate;
			receiptRow.payment_mode = "Cash"
			receiptRow.amount = frm.doc.grand_total;
			refresh_field("receipt_schedule");
		}
		else if (row_count==1)
		{
			//If there is only one row update the amount. If there is more than one row that means there is manual
			//entry and	user need to manage it by themself
			receiptRow.payment_mode = "Cash"
			receiptRow.amount = frm.doc.grand_total;
			refresh_field("receipt_schedule");
		}

		//Update date based on credit_days if there is a credit days change or change in the credit_sales checkbox
		if(refresh || refresh_credit_days)
			receiptRow.date = creditDays ? frappe.datetime.add_days(postingDate, creditDays) : postingDate;
			refresh_field("receipt_schedule");
	}
	else
	{
		frm.doc.receipt_schedule = [];
		refresh_field("receipt_schedule");
	}
}


function update_total_big_display(frm) {

	let netTotal = isNaN(frm.doc.grand_total) ? 0 : parseFloat(frm.doc.grand_total).toFixed(2);

    // Add 'AED' prefix and format net_total for display

	let displayHtml = `<div style="font-size: 25px; text-align: right; color: black;">AED ${netTotal}</div>`;


    // Directly update the HTML content of the 'total_big' field
    frm.fields_dict['total_big'].$wrapper.html(displayHtml);

}

function set_default_payment_mode(frm)
{
	console.log("hi")
	console.log(frm .doc.company)
	if(!frm.doc.on_credit)
	{
		frappe.db.get_value('Company', frm.doc.company,'default_payment_mode_for_sales', function(r){

			if (r && r.default_payment_mode_for_sales) {
							frm.set_value('payment_mode', r.default_payment_mode_for_sales);
			} else {
							frappe.msgprint('Default payment mode for purchase not found.');
			}
		});
	}
	else
	{
		frm.set_value('payment_mode', "");
	}

	frm.set_df_property("credit_days", "hidden", !frm.doc.on_credit);
	frm.set_df_property("payment_mode", "hidden", frm.doc.on_credit);
	frm.set_df_property("payment_account", "hidden", frm.doc.on_credit);

}
frappe.ui.form.on('Credit Note Detail',{
	account(frm, cdt, cdn){
		var child = locals[cdt][cdn];
		if (frm.doc.default_cost_center) {
			frappe.model.set_value(cdt, cdn, 'cost_center', frm.doc.default_cost_center);
		}
	},

  tax_excluded: function(frm, cdt, cdn) {
    frm.trigger("make_taxes_and_totals");
  },
  rate_includes_tax:function(frm,cdt,cdn){
    frm.trigger("make_taxes_and_totals");
  },
  amount: function(frm, cdt, cdn){
    console.log("here")
    frm.trigger("make_taxes_and_totals");
		fill_receipt_schedule(frm)
  },
  tax_rate: function(frm,cdt,cdn){
    frm.trigger("make_taxes_and_totals");
		fill_receipt_schedule(frm)
  }	,
  credit_note_details_add(frm,cdt,cdn){

		let row = frappe.get_doc(cdt, cdn);

		frappe.call(
			{
				method:'digitz_erp.api.settings_api.get_default_tax',
				async:false,
				callback(r){
          			row.tax = r.message

				frappe.call(
					{
					method: 'frappe.client.get_value',
					args: {
						'doctype': 'Tax',
						'filters': { 'tax_name': row.tax },
						'fieldname': ['tax_name', 'tax_rate']
					},
					callback: (r2) => {
						row.tax_rate = r2.message.tax_rate;
						frm.trigger("make_taxes_and_totals");
					}
					});

					frm.refresh_field("credit_note_details");
				}
			}
		);

	},
	credit_note_details_remove(frm,cdt,cdn){
		frm.trigger("make_taxes_and_totals");
	}
})
let create_custom_buttons = function(frm){
	if (frappe.user.has_role('Management')) {
		if(!frm.is_new() && (frm.doc.docstatus == 1)){
		frm.add_custom_button('General Ledgers',() =>{
				general_ledgers(frm)
		}, 'Postings');
		}
	}
}

let general_ledgers = function (frm) {
    frappe.call({
        method: "digitz_erp.api.accounts_api.get_gl_postings",
        args: {
			voucher:frm.doc.doctype,
            voucher_no: frm.doc.name
        },
        callback: function (response) {
            let gl_postings = response.message;

            // Generate HTML content for the popup
            let htmlContent = '<div style="max-height: 400px; overflow-y: auto;">' +
                              '<table class="table table-bordered" style="width: 100%;">' +
                              '<thead>' +
                              '<tr>' +
                              '<th style="width: 20%;">Account</th>' +
                              '<th style="width: 15%;">Debit Amount</th>' +
                              '<th style="width: 15%;">Credit Amount</th>' +
                              '<th style="width: 25%;">Against Account</th>' +
                              '<th style="width: 25%;">Remarks</th>' +
                              '</tr>' +
                              '</thead>' +
                              '<tbody>';

							  gl_postings.forEach(function (gl_posting) {
								// Handling null values for remarks
								let remarksText = gl_posting.remarks || '';  // Replace '' with a default text if you want to show something other than an empty string

								// Ensure debit_amount and credit_amount are treated as floats and format them
								let debitAmount = parseFloat(gl_posting.debit_amount).toFixed(2);
								let creditAmount = parseFloat(gl_posting.credit_amount).toFixed(2);

								htmlContent += '<tr>' +
											   `<td>${gl_posting.account}</td>` +
											   `<td style="text-align: right;">${debitAmount}</td>` +
											   `<td style="text-align: right;">${creditAmount}</td>` +
											   `<td>${gl_posting.against_account}</td>` +
											   `<td>${remarksText}</td>` +
											   '</tr>';
							});

            htmlContent += '</tbody></table></div>';

            // Create and show the dialog
            let d = new frappe.ui.Dialog({
                title: 'General Ledgers',
                fields: [{
                    fieldtype: 'HTML',
                    fieldname: 'general_ledgers_html',
                    options: htmlContent
                }],
                primary_action_label: 'Close',
                primary_action: function () {
                    d.hide();
                }
            });

            // Set custom width for the dialog
            d.$wrapper.find('.modal-dialog').css('max-width', '72%'); // or any specific width like 800px

            d.show();
        }
    });
};
