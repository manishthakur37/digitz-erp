// Copyright (c) 2023, Rupesh P and contributors
// For license information, please see license.
frappe.ui.form.on('Expense Entry', {

  show_a_message: function (frm,message) {
		frappe.call({
			method: 'digitz_erp.api.settings_api.show_a_message',
			args: {
				msg: message
			}
		});
	},
  onload: function(frm)
  {
    assign_defaults(frm);     
  },

  refresh: function(frm) {
    create_custom_buttons(frm)
    frm.set_query('expense_account', 'expense_entry_details', () => {
      return {
        filters: {
          root_type: "Expense",
          is_group: 0
        }
      }
    })

    frm.set_query('payable_account', 'expense_entry_details', () => {
      return {
        filters: {
          root_type: "Liability",
          is_group: 0
        }
      }
    })
	},
  rate_includes_tax: function(frm) {
      frappe.confirm('Are you sure you want to change this setting which will change the tax calculation in the expense entry ?', () => {
      frm.trigger("make_taxes_and_totals");
    })
	},
  validate: function (frm) {

		if(!frm.doc.credit_expense && !frm.doc.payment_mode)
		{
			frappe.throw("Select payment mode.")
		}

		if(!frm.doc.credit_expense && !frm.doc.payment_account)
		{
			frappe.throw("Select payment account.")
		}
	},
  make_taxes_and_totals: function(frm) {

    console.log("from make_tax_and_totals")
		var total_expense_amount = 0;
		var total_tax_amount = 0;
    var grand_total = 0;
		frm.doc.total_expense_amount = 0;
		frm.doc.total_tax_amount = 0;
		frm.doc.grand_total = 0;
		frm.doc.expense_entry_details.forEach(function (entry) {

        if(entry.supplier && entry.expense_account)
        {
          var tax_in_rate = 0;
          var amount_excluded_tax = 0;
          var tax_amount = 0;
          var total = 0;
          amount_excluded_tax = entry.amount
          entry.rate_includes_tax = frm.doc.rate_includes_tax;
          if(entry.tax_rate>0)
          {
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
         else
         {
          tax_amount = 0
         }

          total = amount_excluded_tax + tax_amount;

          frappe.model.set_value(entry.doctype, entry.name, "amount_excluded_tax", amount_excluded_tax);
          frappe.model.set_value(entry.doctype, entry.name, "tax_amount", tax_amount);
          frappe.model.set_value(entry.doctype, entry.name, "total", total);

          total_expense_amount  = total_expense_amount+ entry.amount;

          console.log("entry.amount")
          console.log(entry.amount)
          console.log("total_expense_amount")
          console.log(total_expense_amount)

          total_tax_amount = total_tax_amount + entry.tax_amount;
          grand_total  = grand_total+ entry.total;
        }
		});

    frm.refresh_field("expense_entry_details");

    frm.set_value('total_expense_amount', total_expense_amount);
    frm.set_value('total_tax_amount', total_tax_amount);
    frm.set_value('grand_total', grand_total);
		frm.refresh_field("total_expense_amount");
    frm.refresh_field("total_tax_amount");
    frm.refresh_field("grand_total");

    fill_payment_schedule(frm);

	},
  edit_posting_date_and_time: function(frm) {
		if (frm.doc.edit_posting_date_and_time == 1) {
			frm.set_df_property("posting_date", "read_only", 0);
			frm.set_df_property("posting_time", "read_only", 0);
		}
		else {
			frm.set_df_property("posting_date", "read_only", 1);
			frm.set_df_property("posting_time", "read_only", 1);
		}
	},
  credit_expense: function(frm){

    fill_payment_schedule(frm)
  },
  credit_days(frm)
  {
    fill_payment_schedule(frm)
  },
  work_order:function(frm){

    if(frm.doc.work_order !=undefined)
      {
        frappe.call({
          method: 'frappe.client.get_value',
          args: {
            'doctype': 'Work Order',
            'filter':{'name':frm.doc.work_order},
            'fieldname': 'project'
          },
          callback: (r) => {
            project = r.message.project
            frm.set_value('project',project);            
          }
          });
      }
  },
});

frappe.ui.form.on('Expense Entry Details',{

  expense_account:function(frm,cdt,cdn)
  {
      check_budget_utilization(frm, cdt, cdn,"Account");
      
  },
  amount: function(frm, cdt, cdn){

    console.log("amount")
    frm.trigger("make_taxes_and_totals");

  },
  tax: function(frm,cdt,cdn)
  {

    // frm.trigger("make_taxes_and_totals");

  },
  tax_excluded:function(frm,cdt,cdn)
  {
    let row = frappe.get_doc(cdt, cdn);

    if(row.tax_excluded)
    {
      console.log("tax excluded = true")
      row.tax = "";
      row.tax_rate = 0;

      frm.trigger("make_taxes_and_totals");

      frm.refresh_field("expense_entry_details");
    }
    else
    {

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


    }

  },
  supplier(frm,cdt,cdn)
  {
    let row = frappe.get_doc(cdt, cdn);
    frappe.call(
			{
				method: 'frappe.client.get_value',
				args: {
					'doctype': 'Supplier',
					'filters': { 'name': row.supplier },
					'fieldname': ['credit_days']
				},
				callback: (r) => {

          console.log(r)

          row.credit_days = r.message.credit_days
          console.log(r.message.credit_days)
          frm.refresh_field("expense_entry_details");
        }
      });
  },
  expense_entry_details_add: function(frm,cdt,cdn){
    var child = locals[cdt][cdn];
		if (frm.doc.default_cost_center) {
			frappe.model.set_value(cdt, cdn, 'cost_center', frm.doc.default_cost_center);
		}

    let row = frappe.get_doc(cdt, cdn);
    row.payable_account = frm.doc.default_payable_account
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




    frm.refresh_field("expense_entry_details");

  },
  expense_entry_details_remove:function(frm){

    frm.trigger("make_taxes_and_totals");
  },
  tax_amount: function(frm, cdt, cdn) {

    frm.trigger("make_taxes_and_totals");
  }

});

function update_grand_total(frm) {

  var grand_total = 0;
  if(frm.doc.rate_includes_tax){
    grand_total = frm.doc.total_expense_amount;
  }
  else {
    grand_total = frm.doc.total_expense_amount + frm.doc.total_tax_amount;
  }
  frm.set_value('grand_total', grand_total);
}

function assign_defaults(frm)
{
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
        }
      });

      frappe.call(
        {
          method:'digitz_erp.api.settings_api.get_default_payable_account',
          async:false,
          callback(r){
            frm.set_value('default_payable_account',r.message);
          }
        }
      );


      frappe.db.get_value('Company', frm.doc.company, 'default_credit_purchase', function(r) {

				if (r && r.default_credit_purchase === 1) {
				
					console.log(r.default_credit_purchase)
						frm.set_value('credit_expense', 1);
				}

			});

      // frm.set_value('credit_expense', true);

      set_default_payment_mode(frm);

      frm.refresh_fields();
    }

  }

  function set_default_payment_mode(frm)
{
	console.log("from set_default_payment_mode")

	if(!frm.doc.credit_purchase){

		frappe.db.get_value('Company', frm.doc.company, 'default_payment_mode_for_purchase', function(r) {

			if (r && r.default_payment_mode_for_purchase) {
				frm.set_value('payment_mode', r.default_payment_mode_for_purchase);
			}
			else {
				frappe.msgprint('Default payment mode for purchase not found.');
			}
		});
    }
	else
	{
		frm.set_value('payment_mode','');
	}

	set_payment_visibility(frm)
}

function set_payment_visibility(frm)
{
	frm.set_df_property("credit_days", "hidden", !frm.doc.credit_purchase);
	frm.set_df_property("payment_mode", "hidden", frm.doc.credit_purchase);
	frm.set_df_property("payment_account", "hidden", frm.doc.credit_purchase);
}

  function fill_payment_schedule(frm)
  {

    frm.doc.payment_schedule = [];

    refresh_field("payment_schedule");

    if(frm.doc.credit_expense && frm.doc.expense_entry_details)
    {
        frm.doc.expense_entry_details.forEach(function(expenseRow)
        {
            if(expenseRow)
            {
              console.log("expenseRow")
              console.log(expenseRow)

              var date = expenseRow.credit_days ? frappe.datetime.add_days(expenseRow.expense_date, expenseRow.credit_days) : expenseRow.expense_date;

              var rowFound = false
              frm.doc.payment_schedule.forEach(function(row) {
                if (row){
                  if(row.supplier == expenseRow.supplier && row.date == date)
                  {
                    rowFound = true
                    row.amount = row.amount + expenseRow.total
                  }
                }
              });

              if(!rowFound)
              {
                paymentRow = frappe.model.add_child(frm.doc, "Payment Schedule", "payment_schedule");
                paymentRow.supplier = expenseRow.supplier
                paymentRow.date = date
                paymentRow.payment_mode = "Cash"
                paymentRow.amount = expenseRow.total
              }
          }
        });

        refresh_field("payment_schedule");
    }
    else
    {
      frm.doc.payment_schedule = [];
      refresh_field("payment_schedule");
    }
  }

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
            voucher: frm.doc.doctype,
            voucher_no: frm.doc.name
        },
        callback: function (response) {
            let gl_postings = response.message.gl_postings;
            let totalDebit = parseFloat(response.message.total_debit).toFixed(2);
            let totalCredit = parseFloat(response.message.total_credit).toFixed(2);

            // Generate HTML content for the popup
            let htmlContent = '<div style="max-height: 680px; overflow-y: auto;">' +
                              '<table class="table table-bordered" style="width: 100%;">' +
                              '<thead>' +
                              '<tr>' +
                              '<th style="width: 15%;">Account</th>' +
							  '<th style="width: 25%;">Remarks</th>' +
                              '<th style="width: 10%;">Debit Amount</th>' +
                              '<th style="width: 10%;">Credit Amount</th>' +
							  '<th style="width: 10%;">Party</th>' +
                              '<th style="width: 10%;">Against Account</th>' +                              
                              '<th style="width: 10%;">Project</th>' +
                              '<th style="width: 10%;">Cost Center</th>' +                              
                              '</tr>' +
                              '</thead>' +
                              '<tbody>';

			console.log("gl_postings",gl_postings)

            gl_postings.forEach(function (gl_posting) {
                let remarksText = gl_posting.remarks || '';
                let debitAmount = parseFloat(gl_posting.debit_amount).toFixed(2);
                let creditAmount = parseFloat(gl_posting.credit_amount).toFixed(2);

                htmlContent += '<tr>' +
                               `<td>${gl_posting.account}</td>` +
							   `<td>${remarksText}</td>` +
                               `<td style="text-align: right;">${debitAmount}</td>` +
                               `<td style="text-align: right;">${creditAmount}</td>` +
							   `<td>${gl_posting.party}</td>` +
                               `<td>${gl_posting.against_account}</td>` +                               
                               `<td>${gl_posting.project}</td>` +
                               `<td>${gl_posting.cost_center}</td>` +
                               
                               '</tr>';
            });

            // Add totals row
            htmlContent += '<tr>' +
                           '<td style="font-weight: bold;">Total</td>' +
						   '<td></td>'+
                           `<td style="text-align: right; font-weight: bold;">${totalDebit}</td>` +
                           `<td style="text-align: right; font-weight: bold;">${totalCredit}</td>` +
                           '<td colspan="5"></td>' +
                           '</tr>';

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
            d.$wrapper.find('.modal-dialog').css('max-width', '90%'); 

            d.show();
        }
    });
};
  
function check_budget_utilization(frm, cdt, cdn, reference_type) {
  const row = frappe.get_doc(cdt, cdn);

  // Ensure the item field is filled before proceeding
  if (!row.expense_account) {
      return;
  }

  console.log("project",frm.doc.project)
  
  // Call server method to get budget details
  frappe.call({
      method: "digitz_erp.api.accounts_api.get_balance_budget_value",
      args: {
          reference_type: reference_type,
          reference_value: row.expense_account,
          transaction_date: frm.doc.transaction_date || frappe.datetime.nowdate(),
          company: frm.doc.company,
          project: frm.doc.project || null,
          cost_center: frm.doc.cost_center || null
      },
      callback: function (response) {
          if (response && response.message) {
              const result = response.message;

              // Log the response for debugging
              console.log("Budget Result:", result);

              if (!result.no_budget) {
                  // Display budget details if available
                  const details = result.details || {};
                  const budgetMessage = `
                      <strong>Budget Against:</strong> ${details["Budget Against"] || "N/A"}<br>
                      <strong>Reference Type:</strong> ${details["Reference Type"] || "N/A"}<br>
                      <strong>Budget Amount:</strong> ${details["Budget Amount"] || 0}<br>
                      <strong>Utilized Amount:</strong> ${details["Used Amount"] || 0}<br>
                      <strong>Remaining Balance:</strong> ${details["Available Balance"] || 0}
                  `;

                  // Custom method to display the message (replace with your own if needed)
                 
                  frm.events.show_a_message(frm,budgetMessage);
                  
              }
          } else {
              // Handle case where no response is received
              frappe.msgprint({
                  title: __("Error"),
                  indicator: "red",
                  message: __("No response received from the server.")
              });
          }
      }
  });
}