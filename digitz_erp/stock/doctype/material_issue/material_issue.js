// Copyright (c) 2024, Rupesh P and contributors
// For license information, please see license.txt

frappe.ui.form.on("Material Issue", {

	refresh: function(frm) {
		create_custom_buttons(frm)
	},

	setup:function(frm)
	{
		// frm.set_query("warehouse", function() {
		// 	return {
		// 		"filters": {
		// 			"disabled": 0
		// 		}
		// 	};
		// });
		// frm.set_query("project", function() {
		// 	return {
		// 		"filters": {
		// 			"disabled": 0
		// 		}
		// 	};
		// });

		// frm.fields_dict['items'].grid.get_field('warehouse').get_query = function(doc, cdt, cdn) {
        //     return {
        //         filters: {
        //             disabled: 0
        //         }
        //     };
		// }
		// frm.fields_dict['items'].grid.get_field('project').get_query = function(doc, cdt, cdn) {
        //     return {
        //         filters: {
        //             disabled: 0
        //         }
        //     };
		// }
	},
	assign_defaults(frm)
	{
		frm.trigger("get_default_company_and_warehouse");
	},

	edit_posting_date_and_time(frm) {

		//console.log(frm.doc.edit_posting_date_and_time);
		console.log(frm.doc.edit_posting_date_and_time);

		if (frm.doc.edit_posting_date_and_time == 1) {
			frm.set_df_property("posting_date", "read_only", 0);
			frm.set_df_property("posting_time", "read_only", 0);
		}
		else {
			frm.set_df_property("posting_date", "read_only", 1);
			frm.set_df_property("posting_time", "read_only", 1);
		}
	},
	get_default_company_and_warehouse(frm) {
		var default_company = ""
		console.log("From Get Default Warehouse Method in the parent form")

		frappe.call({
			method: 'frappe.client.get_value',
			args: {
				'doctype': 'Global Settings',
				'fieldname': 'default_company'
			},
			callback: (r) => {

				default_company = r.message.default_company
				frm.doc.company = r.message.default_company
				frm.refresh_field("company");
				// frappe.call(
				// 	{
				// 		method: 'frappe.client.get_value',
				// 		args: {
				// 			'doctype': 'Company',
				// 			'filters': { 'company_name': default_company },
				// 			'fieldname': ['default_warehouse', 'rate_includes_tax']
				// 		},
				// 		callback: (r2) => {
				// 			console.log(r2);
				// 			// frm.doc.warehouse = r2.message.default_warehouse;
				// 			frm.refresh_field("warehouse");
				// 		}
				// 	}

				// )
			}
		})
	},
	get_item_stock_balance(frm) {

		frm.doc.selected_item_stock_qty_in_the_warehouse =""
		frm.refresh_field("selected_item_stock_qty_in_the_warehouse");

		frappe.call(
			{
				method: 'digitz_erp.api.items_api.get_stock_for_item_project',
				async: false,
				args: {
					'item': row.item,
					'project': frm.warehouse,
					'posting_date': frm.doc.posting_date,
					'posting_time': frm.doc.posting_time
				},
				callback(r) {
					if(typeof(r.message.stock_qty) !='undefined')
						frm.doc.selected_item_stock_qty_in_the_warehouse ="Stock in " + frm.warehouse + ": " +  r.message.stock_qty

					frm.refresh_field("selected_item_stock_qty_in_the_warehouse");
				}
			});

			frappe.call(
				{
					method: 'digitz_erp.api.items_api.get_stock_for_item_project',
					async: false,
					args: {
						'item': row.item,
						'project': frm.project,
						'posting_date': frm.doc.posting_date,
						'posting_time': frm.doc.posting_time
					},
					callback(r) {
						if(typeof(r2.message.stock_qty) !='undefined')
							frm.doc.selected_item_stock_qty_in_the_warehouse = frm.doc.selected_item_stock_qty_in_the_warehouse + ", " + frm.project + ": " +  r2.message.stock_qty
							frm.refresh_field("selected_item_stock_qty_in_the_warehouse");
						}
				});
	},
	make_totals(frm) {
		console.log("from make totals..")
		frm.clear_table("taxes");
		frm.refresh_field("taxes");

		var gross_total = 0;
		var tax_total = 0;
		var net_total = 0;
		var discount_total = 0;

		//Avoid Possible NaN

		frm.doc.net_total = 0;
		net_total = 0

		frm.doc.items.forEach(function (entry) {

				entry.net_amount = entry.qty * entry.rate
				net_total= net_total + entry.net_amount

				entry.qty_in_base_unit = entry.qty * entry.conversion_factor;
				entry.rate_in_base_unit = entry.rate / entry.conversion_factor;
			})

			frm.doc.net_total = net_total
			frm.refresh_field("items");
			frm.refresh_field("net_total");
		},
		get_item_units(frm) {

			frappe.call({
				method: 'digitz_erp.api.items_api.get_item_uoms',
				async: false,
				args: {
					item: frm.item
				},
				callback: (r) => {

					console.log(r)
					var units = ""
					for(var i = 0; i < r.message.length; i++)
					{
						if(i==0)
						{
							units = r.message[i].unit
						}
						else
						{
							units = units + ", " + r.message[i].unit
						}
					}

					frm.doc.item_units = "Unit(s) for "+ frm.item +": " +units
					frm.refresh_field("item_units");
				}
			})
		}
});

frappe.ui.form.on("Material Issue", "onload", function (frm) {

	frm.trigger('assign_defaults')
})

frappe.ui.form.on('Material Issue Item', {

	item(frm, cdt, cdn) {

		let row = frappe.get_doc(cdt, cdn);
		frappe.call(
			{
			method: 'frappe.client.get_value',
					args: {
						'doctype': 'Item',
						'filters': { 'item_code': row.item },
						'fieldname': ['item_name', 'base_unit', 'tax', 'tax_excluded']
					},
					callback: (r) => {

						row.item_name = r.message.item_name;
						row.base_unit = r.message.base_unit;
						row.unit = r.message.base_unit;
						row.conversion_factor = 1;
						frm.item = row.item
						row.warehouse = frm.doc.warehouse
						row.project = frm.doc.project
						row.display_name = row.item_name

						frm.warehouse = row.warehouse
						frm.project = row.project

						frm.trigger("get_item_stock_balance");
						frm.refresh_field("items");

						frappe.call(
							{
								method: 'digitz_erp.api.items_api.get_item_valuation_rate',
								async: false,
								args: {
									'item': row.item,
									'posting_date': frm.doc.posting_date,
									'posting_time': frm.doc.posting_time
								},
								callback(r) {
									console.log("Valuation rate in console")
									console.log(r.message)

									if(r.message == 0)
									{
										let currency = ""
										console.log("before call digitz_erp.api.settings_api.get_default_currency")
										frappe.call(
										{
											method:'digitz_erp.api.settings_api.get_default_currency',
											async:false,
											callback(r){
												console.log(r)
												currency = r.message
												console.log("currency")
												console.log(currency)
										}
										}
										);

										frappe.call(
										{
										method: 'digitz_erp.api.item_price_api.get_item_price',
										async: false,

										args: {
											'item': row.item,
											'price_list': 'Standard Buying',
											'currency': currency,
											'date': frm.doc.posting_date
										},
										callback(r) {
											console.log("digitz_erp.api.item_price_api.get_item_price")
											console.log(r)
											row.rate = parseFloat(r.message);
											row.rate_in_base_unit = parseFloat(r.message);
										}
										});

									}
									else
									{
										row.rate = r.message
										row.rate_in_base_unit = r.message
										frm.refresh_field("items");
									}
								}
							});
					}
				});

		console.log("Before get valuation rate for the item")

		frm.item = row.item
		frm.trigger("get_item_units");
	},
	warehouse(frm, cdt, cdn) {

		let row = frappe.get_doc(cdt, cdn);
		frm.item = row.item
		frm.warehouse = row.warehouse
		frm.project = row.project
		frm.trigger("get_item_stock_balance");
	},
	project(frm, cdt, cdn) {

		let row = frappe.get_doc(cdt, cdn);
		frm.item = row.item
		frm.warehouse = row.warehouse
		frm.project = row.project
		frm.trigger("get_item_stock_balance");
	},
	items_add(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		row.warehouse = frm.doc.warehouse
		row.project = frm.doc.project
		frm.refresh_field("items");
	},
	items_remove(frm, cdt, cdn) {
		frm.trigger("make_totals")
	},
	qty(frm, cdt, cdn) {

		frm.trigger("make_totals")
	},
	rate(frm, cdt, cdn) {

		frm.trigger("make_totals")
	},
	unit(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);

		frappe.call(
			{
				method: 'digitz_erp.api.items_api.get_item_uom',
				async: false,
				args: {
					item: row.item,
					unit: row.unit
				},
				callback(r) {
					if (r.message.length == 0) {
						frappe.msgprint("Invalid unit, Unit does not exists for the item.");
						row.unit = row.base_unit;
						row.conversion_factor = 1;
					}
					else {
						console.log(r.message[0].conversion_factor);
						row.conversion_factor = r.message[0].conversion_factor;
						row.rate = row.rate_in_base_unit * row.conversion_factor;
						//frappe.confirm('Rate converted for the unit selected. Do you want to convert the qty as well ?',
						//() => {
						//row.qty = row.qty/ row.conversion_factor;
						//})
					}
					frm.trigger("make_totals");

					frm.refresh_field("items");
				}

			}
		);
	},
}
);


let create_custom_buttons = function(frm){
	if (frappe.user.has_role('Management')) {
		if(!frm.is_new() && (frm.doc.docstatus == 1)){

			frm.add_custom_button('Project Stock Ledgers',() =>{
				stock_ledgers(frm)
		}, 'Postings');
		}
	}
}
let stock_ledgers = function (frm) {
    frappe.call({
        method: "digitz_erp.api.accounts_api.get_stock_ledgers_project",
        args: {
			voucher: frm.doc.doctype,
            voucher_no: frm.doc.name
        },
        callback: function (response) {
            let project_stock_ledgers_data = response.message;

            // Generate HTML content for the popup
            let htmlContent = '<div style="max-height: 400px; overflow-y: auto;">' +
                              '<table class="table table-bordered" style="width: 100%;">' +
                              '<thead>' +
                              '<tr>' +
                              '<th style="width: 10%;">Item Code</th>' +
							  '<th style="width: 20%;">Item Name</th>' +
                              '<th style="width: 15%;">Project</th>' +
                              '<th style="width: 20%;">Consumed Qty</th>' +
                              '<th style="width: 15%;">Valuation Rate</th>' +
                              '<th style="width: 15%;">Balance Qty</th>' +
                              '<th style="width: 15%;">Balance Value</th>' +
                              '</tr>' +
                              '</thead>' +
                              '<tbody>';

            // Loop through the data and create rows
            project_stock_ledgers_data.forEach(function (ledger) {
                htmlContent += '<tr>' +
                               `<td><a href="/app/item/${ledger.item}" target="_blank">${ledger.item}</a></td>` +
							   `<td>${ledger.item_name}</td>` +
                               `<td>${ledger.project}</td>` +
                               `<td>${ledger.consumed_qty}</td>` +
                               `<td>${ledger.valuation_rate}</td>` +
                               `<td>${ledger.balance_qty}</td>` +
                               `<td>${ledger.balance_value}</td>` +
                               '</tr>';
            });

            htmlContent += '</tbody></table></div>';

            // Create and show the dialog
            let d = new frappe.ui.Dialog({
                title: 'Project Stock Ledgers',
                fields: [{
                    fieldtype: 'HTML',
                    fieldname: 'stock_ledgers_html',
                    options: htmlContent
                }],
                primary_action_label: 'Close',
                primary_action: function () {
                    d.hide();
                }
            });

            // Set custom width for the dialog
            d.$wrapper.find('.modal-dialog').css('max-width', '85%'); // or any specific width like 800px

            d.show();
        }
    });
};
