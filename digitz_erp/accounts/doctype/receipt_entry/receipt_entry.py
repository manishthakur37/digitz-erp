# Copyright (c) 2022, Rupesh P and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from digitz_erp.api.receipt_entry_api import get_allocations_for_sales_invoice ,get_allocations_for_sales_return, get_allocations_for_credit_note,get_allocations_for_progressive_sales_invoice
from datetime import datetime, timedelta
from digitz_erp.api.document_posting_status_api import init_document_posting_status, update_posting_status
from digitz_erp.api.gl_posting_api import update_accounts_for_doc_type, delete_gl_postings_for_cancel_doc_type
from digitz_erp.api.bank_reconciliation_api import create_bank_reconciliation, cancel_bank_reconciliation
from digitz_erp.api.settings_api import add_seconds_to_time


class ReceiptEntry(Document):

	def Voucher_In_The_Same_Time(self):
		possible_invalid= frappe.db.count('Receipt Entry', {'posting_date': ['=', self.posting_date], 'posting_time':['=', self.posting_time]})
		return possible_invalid
	
	def Set_Posting_Time_To_Next_Second(self):
		# Add 12 seconds to self.posting_time and update it
		self.posting_time = add_seconds_to_time(str(self.posting_time), seconds=12)
  
	def assign_customers(self):
		# Assuming receipt_entry_details is a list of dictionaries containing receipt details
		receipt_details = self.receipt_entry_details

		# Initialize an empty list to store customer names
		customers = []

		# Check if there are any receipt details
		if receipt_details:
			# Loop through each detail in the receipt details
			for receipt_detail in receipt_details:
				# Check if 'customer' key exists and has a value
				if receipt_detail.customer:
					# Append the customer name to the customers list
					if receipt_detail.customer not in customers:
						customers.append(receipt_detail.customer)

		# Join all customer names into a single string separated by commas
		customers_str = ", ".join(customers)
		self.customers = customers_str

	def assign_missing_reference_nos(self):
		if self.payment_mode != "Bank":
				return
		receipt_details = self.receipt_entry_details

		if receipt_details:
			for receipt_detail in receipt_details:
				if not receipt_detail.reference_no:
					if(self.reference_no):
						receipt_detail.reference_no = self.reference_no

				if not receipt_detail.reference_date:
					if(self.reference_date):
						receipt_detail.reference_date = self.reference_date

	def before_validate(self):

		if(self.Voucher_In_The_Same_Time()):

				self.Set_Posting_Time_To_Next_Second()

				if(self.Voucher_In_The_Same_Time()):
					self.Set_Posting_Time_To_Next_Second()

					if(self.Voucher_In_The_Same_Time()):
						self.Set_Posting_Time_To_Next_Second()

						if(self.Voucher_In_The_Same_Time()):
							frappe.throw("Voucher with same time already exists.")

		self.show_allocations = False
		self.assign_missing_reference_nos()
		self.clean_deleted_allocations()
		self.postings_start_time = datetime.now()
		self.assign_customers()
		self.validate_receipt_entry()
  
	def validate_receipt_entry(frm):
		pass
     
		# for row in frm.get("receipt_entry_details"):  # Loop through each row in the child table
		# 	if row.reference_type == "Sales Order":
		# 		# Fetch the account linked to this row
		# 		account = frappe.get_doc("Account", row.account)
		# 		# if account.root_type != "Liability":
		# 			# frappe.throw(_("Account selected must have 'root_type' as 'Liability' when 'reference_type' is 'Sales Order'."))
		# 	else:
		# 		# For other reference_types, check that the root_type is "Asset"
		# 		account = frappe.get_doc("Account", row.account)
		# 		if account.root_type != "Asset":
		# 			frappe.throw(_("Account selected must have 'root_type' as 'Asset' when 'reference_type' is not 'Sales Order'."))



	def validate(self):

		self.validate_doc_status()
		self.check_reference_numbers()
		self.check_allocations_and_totals()
		self.check_excess_allocation()
		self.validate_multiple_sales_orders()
  
	def revert_for_advance_receipt(self):
		"""
		Reverts updates made to Sales Invoice and Sales Order fields during advance receipt processing.
		This method resets:
		- 'advance_received_with_sales_order' in Sales Invoice
		- 'advance_received_with_sales_invoice' in Sales Order
		"""
		# Loop through the allocation table in the Receipt Entry
		for allocation in self.receipt_allocation:
			# Case 1: Allocation is for 'Sales Order'
			if allocation.reference_type == "Sales Order":
				sales_order = allocation.reference_name
				
				# Find the corresponding Sales Invoices linked to this Sales Order
				sales_invoices = frappe.get_all(
					"Sales Invoice",
					filters={
						"sales_order": sales_order,
						"for_advance_payment": 1  # True in database
					},
					fields=["name"]
				)
				
				# Reset the 'advance_received_with_sales_order' field in each linked Sales Invoice
				for invoice in sales_invoices:
					frappe.db.set_value("Sales Invoice", invoice["name"], "advance_received_with_sales_order", 0)

			# Case 2: Allocation is for 'Sales Invoice'
			elif allocation.reference_type == "Sales Invoice":
				sales_invoice = allocation.reference_name

				# Check if the Sales Invoice is marked as 'for_advance_payment'
				for_advance_payment = frappe.db.get_value("Sales Invoice", sales_invoice, "for_advance_payment")
				
				if for_advance_payment:
					# Get the linked Sales Order for the Sales Invoice
					sales_order = frappe.db.get_value("Sales Invoice", sales_invoice, "sales_order")
					
					if sales_order:
						# Reset the 'advance_received_with_sales_invoice' field in the Sales Order
						frappe.db.set_value("Sales Order", sales_order, "advance_received_with_sales_invoice", 0)

		# Commit changes to the database
		frappe.db.commit()

  
	def update_for_advance_receipt(self):
		"""
		Updates Sales Invoice and Sales Order fields based on allocations in the Receipt Entry
		for advance receipt scenarios.
		"""
		# Loop through the allocation table in the Receipt Entry
		for allocation in self.receipt_allocation:
			# Case 1: Allocation is for 'Sales Order'
			if allocation.reference_type == "Sales Order":
				sales_order = allocation.reference_name
				
				# Find the corresponding Sales Invoices linked to this Sales Order
				sales_invoices = frappe.get_all(
					"Sales Invoice",
					filters={
						"sales_order": sales_order,
						"for_advance_payment": 1  # True in database
					},
					fields=["name"]
				)
				
				# Update the 'advance_received_with_sales_order' field in each linked Sales Invoice
				for invoice in sales_invoices:
					frappe.db.set_value("Sales Invoice", invoice["name"], "advance_received_with_sales_order", 1)

			# Case 2: Allocation is for 'Sales Invoice'
			elif allocation.reference_type == "Sales Invoice":
				sales_invoice = allocation.reference_name

				# Check if the Sales Invoice is marked as 'for_advance_payment'
				for_advance_payment = frappe.db.get_value("Sales Invoice", sales_invoice, "for_advance_payment")
				
				if for_advance_payment:
					# Get the linked Sales Order for the Sales Invoice
					sales_order = frappe.db.get_value("Sales Invoice", sales_invoice, "sales_order")
					
					if sales_order:
						# Update the 'advance_received_with_sales_invoice' field in the Sales Order
						frappe.db.set_value("Sales Order", sales_order, "advance_received_with_sales_invoice", 1)

		# Commit changes to the database
		frappe.db.commit()

	
	def validate_multiple_sales_orders(self):
 
		sales_order_count = sum(1 for row in self.receipt_entry_details if row.reference_type == "Sales Order")

		# If more than one row has reference_type = 'Sales Order', raise an error
		if sales_order_count > 1:
			frappe.throw(
			_("You cannot allocate multiple rows with 'Sales Order' as the reference type. Please keep only one row with 'Sales Order'.")
			)

	def clean_deleted_allocations(self):

		allocations = self.receipt_allocation
		#print('allocations :', allocations)

		if(allocations):
			for allocation in allocations[:]:

				receipt_details = self.receipt_entry_details
				allocation_exist = False
				if receipt_details:
					for receipt_entry in receipt_details:
						if receipt_entry.customer == allocation.customer and receipt_entry.allocated_amount and receipt_entry.allocated_amount>0:
							allocation_exist= True
					if allocation_exist==False:
						self.receipt_allocation.remove(allocation)

	def check_reference_numbers(self):

		if self.payment_mode != "Bank":
			return

		receipt_details = self.receipt_entry_details

		if receipt_details:
			for receipt_detail in receipt_details:
				if not receipt_detail.reference_no:
					if(not self.reference_no):
						frappe.throw("Reference No is mandatory for Bank receipts")
				if not receipt_detail.reference_date:
					if(not self.reference_date):
						frappe.throw("Reference Date is mandatory for Bank receipts")

	def validate_doc_status(self):

		if self.amount == 0:
			frappe.throw("Cannot save the document with out valid inputs.")

		if not self.receipt_entry_details:
			frappe.throw("No valid receipt entries found to save the document")

		for receipt_entry in self.receipt_entry_details:
			if receipt_entry.receipt_type == "Other" and (receipt_entry.reference_type == "Sales Invoice"):
				messge = """Invalid reference type found at line {0} """.format(receipt_entry.idx)
				frappe.throw(messge)

			if receipt_entry.receipt_type == "Other" and receipt_entry.customer:
				messge = """Customer should not be selected with the payment type 'Other', at line {0} """.format(receipt_entry.idx)
				frappe.throw(messge)

			if receipt_entry.receipt_type == "Customer" and (not receipt_entry.customer):
				messge = """Customer is mandatory for the payment type Customer, at line {0} """.format(receipt_entry.idx)
				frappe.throw(messge)

			if receipt_entry.reference_type == "Sales Invoice"  and (not receipt_entry.customer):
				messge = """Customer is mandatory for the referene type Sales Invoice, at line {0} """.format(receipt_entry.idx)
				frappe.throw(messge)

			# if receipt_entry.reference_type == "Sales Invoice" and receipt_entry.customer and receipt_entry.allocated_amount ==0:

			# 	messge = """Allocation not found for the payment at line {0} """.format(receipt_entry.idx)
			# 	frappe.throw(messge)


    # Cleaning the deleted allocations is crucial, so this method should call even though it cleans with the client side javascript code
	def clean_deleted_allocations(self):

		allocations = self.receipt_allocation
		#print("len(allocations)")
		#print(len(allocations))

		if(allocations):
			for allocation in allocations[:]:
				#print("allocation.customer")
				#print(allocation.customer)
				receipt_details = self.receipt_entry_details
				allocation_exist = False
				if(receipt_details):
					for receipt_entry in receipt_details:
						if receipt_entry.customer == allocation.customer and receipt_entry.allocated_amount and receipt_entry.allocated_amount>0:
							allocation_exist= True
					if allocation_exist==False:
						self.receipt_allocation.remove(allocation)

	def check_allocations_and_totals(self):
		receipt_details = self.receipt_entry_details
		total_amount_in_rows =0
		total_allocated_in_rows = 0

		if(receipt_details):
			for receipt_detail in receipt_details:

				total_amount_in_rows = total_amount_in_rows+ receipt_detail.amount if receipt_detail.amount else 0

				if receipt_detail.receipt_type != "Customer":
					continue

				# If there is an allocation in the lineitem make sure the amount and allocated amount are same
				if(receipt_detail.allocated_amount and receipt_detail.allocated_amount>0):
					if(receipt_detail.amount!= receipt_detail.allocated_amount):
						frappe.throw("Allocated amount mismatch.")

				if(receipt_detail.allocated_amount):
					total_allocated_in_rows = total_allocated_in_rows +  receipt_detail.allocated_amount


		amount = 0
		if self.amount is not None:
			amount = self.amount

		#print("amount")
		#print(amount)
		#print("total_amount_in_rows")
		#print(total_amount_in_rows)
		if(amount != total_amount_in_rows):
			frappe.throw("Mismatch in total amount. Please check the document inputs")

		allocated_amount = 0

		if self.allocated_amount is not None:
			allocated_amount = self.allocated_amount

		#print("allocated_amount")
		#print(allocated_amount)
		#print("total_allocated_in_rows")
		#print(total_allocated_in_rows)
		# Both values are not None, perform the comparison
		# if allocated_amount != total_allocated_in_rows:
			# frappe.throw("Mismatch in total allocated amount. Please check the document inputs")


	def check_excess_allocation(self):
		#print("from check excces allocation")
		allocations = self.receipt_allocation

		if(allocations):
			for allocation in allocations:
				if(allocation.paying_amount>0):
					is_new = self.is_new()
					#print("self.is_new()")
					#print(self.is_new())

					receipt_no = self.name
					if self.is_new():
						receipt_no = ""
					#print("receipt_no")
					#print(receipt_no)

					if(allocation.reference_type == "Sales Invoice"):
						previous_paid_amount = 0
						allocations_exists = get_allocations_for_sales_invoice(allocation.reference_name, receipt_no)
      
					if(allocation.reference_type == "Progressive Sales Invoice"):
						previous_paid_amount = 0
						allocations_exists = get_allocations_for_progressive_sales_invoice(allocation.reference_name, receipt_no)

					if(allocation.reference_type == "Sales Return"):
						previous_paid_amount = 0
						allocations_exists = get_allocations_for_sales_return(allocation.reference_name, receipt_no)

						for existing_allocation in allocations_exists:
							previous_paid_amount = previous_paid_amount +  existing_allocation.paying_amount

						if allocation.paying_amount > allocation.total_amount-previous_paid_amount:
							#print("throws error")
							frappe.throw("Excess allocation for the invoice numer " + allocation.reference_name )

	def on_update(self):

		self.update_sales_invoices()
		self.update_progressive_sales_invoices()
		self.update_sales_return()
		self.update_credit_note()
		self.update_for_advance_receipt()

	def on_submit(self):
		# self.do_posting()
		init_document_posting_status(self.doctype,self.name)

		turn_off_background_job = frappe.db.get_single_value("Global Settings",'turn_off_background_job')

		# if(frappe.session.user == "Administrator" and turn_off_background_job):
		# 	self.do_postings_on_submit()
		# else:
		# 	frappe.enqueue(self.do_postings_on_submit,queue="long")

		self.do_postings_on_submit()
  
	def do_postings_on_submit(self):

		self.insert_gl_records()
		update_accounts_for_doc_type('Receipt Entry',self.name)
		update_posting_status(self.doctype,self.name, 'gl_posted_time')
		update_posting_status(self.doctype,self.name,'posting_status','Completed')
		create_bank_reconciliation("Receipt Entry", self.name)

	def update_sales_invoices(self):
		
		allocations = self.receipt_allocation

		if(allocations):
			for allocation in allocations:

				if allocation.reference_type != "Sales Invoice":
					continue

				if(allocation.paying_amount>0):

					receipt_no = self.name
					if self.is_new():
						receipt_no = ""

					previous_paid_amount = 0
					allocations_exists = get_allocations_for_sales_invoice(allocation.reference_name, receipt_no)

					for existing_allocation in allocations_exists:
						previous_paid_amount = previous_paid_amount +  existing_allocation.paying_amount

					invoice_total = previous_paid_amount + allocation.paying_amount

					frappe.db.set_value("Sales Invoice", allocation.reference_name, {'paid_amount': invoice_total})

					invoice_amount = frappe.db.get_value("Sales Invoice", allocation.reference_name,["rounded_total"])
					if(round(invoice_amount,2) > round(invoice_total,2)):
						frappe.db.set_value("Sales Invoice", allocation.reference_name, {'payment_status': "Partial"})
					elif round(invoice_amount,2) == round(invoice_total,2):
						frappe.db.set_value("Sales Invoice", allocation.reference_name, {'payment_status': "Paid"})

	def update_progressive_sales_invoices(self):
		
		allocations = self.receipt_allocation

		if(allocations):
			for allocation in allocations:

				if allocation.reference_type != "Progressive Sales Invoice":
					continue

				if(allocation.paying_amount>0):

					receipt_no = self.name
					if self.is_new():
						receipt_no = ""

					previous_paid_amount = 0
					allocations_exists = get_allocations_for_progressive_sales_invoice(allocation.reference_name, receipt_no)

					for existing_allocation in allocations_exists:
						previous_paid_amount = previous_paid_amount +  existing_allocation.paying_amount

					invoice_total = previous_paid_amount + allocation.paying_amount

					frappe.db.set_value("Progressive Sales Invoice", allocation.reference_name, {'paid_amount': invoice_total})

					invoice_amount = frappe.db.get_value("Progressive Sales Invoice", allocation.reference_name,["rounded_total"])
					if(round(invoice_amount,2) > round(invoice_total,2)):
						frappe.db.set_value("Progressive Sales Invoice", allocation.reference_name, {'payment_status': "Partial"})
					elif round(invoice_amount,2) == round(invoice_total,2):
						frappe.db.set_value("Progressive Sales Invoice", allocation.reference_name, {'payment_status': "Paid"})



	def update_sales_return(self):
		allocations = self.receipt_allocation

		if(allocations):
			for allocation in allocations:

				if allocation.reference_type != "Sales Return":
					continue

				if(allocation.paying_amount>0):

					receipt_no = self.name
					if self.is_new():
						receipt_no = ""

					previous_paid_amount = 0
					allocations_exists = get_allocations_for_sales_return(allocation.reference_name, receipt_no)

					for existing_allocation in allocations_exists:
						previous_paid_amount = previous_paid_amount +  existing_allocation.paying_amount

					invoice_total = previous_paid_amount + allocation.paying_amount

					frappe.db.set_value("Sales Return", allocation.reference_name, {'paid_amount': invoice_total})

	def update_credit_note(self):
		allocations = self.receipt_allocation

		if(allocations):
			for allocation in allocations:

				if allocation.reference_type != "Credit Note":
					continue

				if(allocation.paying_amount>0):

					receipt_no = self.name
					if self.is_new():
						receipt_no = ""

					previous_paid_amount = 0
					allocations_exists = get_allocations_for_credit_note(allocation.reference_name, receipt_no)

					for existing_allocation in allocations_exists:
						previous_paid_amount = previous_paid_amount +  existing_allocation.paying_amount

					invoice_total = previous_paid_amount + allocation.paying_amount

					frappe.db.set_value("Credit Note", allocation.reference_name, {'paid_amount': invoice_total})
     
    
	def check_projects(self):
		projects = False
		for row in self.receipt_entry_details:
			if row.project:
				projects = True
				break

		if not projects:
			for row in self.receipt_allocation:
				if row.project:
					projects = True
					break

		return projects

    
	def insert_gl_records(self):

		if self.check_projects():
			print("Calling insert_gl_records_for_projects")
			self.insert_gl_records_for_projects()
			return

		default_company = frappe.db.get_single_value(
			"Global Settings", "default_company")

		default_accounts = frappe.get_value("Company", default_company, ['default_receivable_account', 'default_inventory_account',
		 																	'default_income_account', 'cost_of_goods_sold_account', 'round_off_account', 'tax_account'], as_dict=1)
		idx = 0

		receipt_details = self.receipt_entry_details
  
		for_return_amount = 0
  
		if(receipt_details):
			for receipt_entry in receipt_details:
				if(receipt_entry.receipt_type == "Customer"):
        
					remarks = f"{self.payment_mode} receipt from {receipt_entry.customer}"
     
					idx = idx + 1
					gl_doc = frappe.new_doc('GL Posting')
					gl_doc.voucher_type = "Receipt Entry"
					gl_doc.voucher_no = self.name
					gl_doc.idx = idx
					gl_doc.posting_date = self.posting_date
					gl_doc.posting_time = self.posting_time
					gl_doc.account = receipt_entry.account
		
					if (receipt_entry.reference_type == "Sales Return") or (receipt_entry.reference_type == "Credit Note") : 
						gl_doc.debit_amount = receipt_entry.amount
						for_return_amount += receipt_entry.amount
					else:
						gl_doc.credit_amount = receipt_entry.amount
				
					gl_doc.party_type = "Customer"
					gl_doc.party = receipt_entry.customer
					gl_doc.against_account = self.account
					gl_doc.remarks = self.remarks if self.remarks else remarks
					gl_doc.insert()

				else: #Other Receipt Type
        
					remarks = f"{self.payment_mode} receipt"
     
					idx = idx + 1
					gl_doc = frappe.new_doc('GL Posting')
					gl_doc.voucher_type = "Receipt Entry"
					gl_doc.voucher_no = self.name
					gl_doc.idx = idx
					gl_doc.posting_date = self.posting_date
					gl_doc.posting_time = self.posting_time
					gl_doc.account = receipt_entry.account if receipt_entry.account else default_accounts.default_receivable_account
					gl_doc.credit_amount = receipt_entry.amount
					gl_doc.against_account = self.account
					gl_doc.remarks = self.remarks if self.remarks else remarks
					gl_doc.insert()
     
		# Credit for the return with payment mode (cash/bank/etc).
		if for_return_amount >0:
			remarks = f"{self.payment_mode} receipt adjustment for return"

			gl_doc = frappe.new_doc('GL Posting')
			gl_doc.voucher_type = "Receipt Entry"
			gl_doc.voucher_no = self.name
			gl_doc.idx = idx
			gl_doc.posting_date = self.posting_date
			gl_doc.posting_time = self.posting_time
			gl_doc.account = self.account
			gl_doc.credit_amount = for_return_amount
			gl_doc.against_account = self.GetAccountForTheHighestAmountInPayments()
			gl_doc.remarks = self.remarks if self.remarks else remarks		
			gl_doc.insert()
   
		# Avoid zero
		# Debit for the payment mode cash/bank/etc
		if (self.amount -for_return_amount) > 0:
			remarks = f"{self.payment_mode} receipt"
			gl_doc = frappe.new_doc('GL Posting')
			gl_doc.voucher_type = "Receipt Entry"
			gl_doc.voucher_no = self.name
			gl_doc.idx = idx
			gl_doc.posting_date = self.posting_date
			gl_doc.posting_time = self.posting_time
			gl_doc.account = self.account
			gl_doc.debit_amount = self.amount -for_return_amount
			gl_doc.against_account = self.GetAccountForTheHighestAmountInPayments()
			gl_doc.remarks = self.remarks if self.remarks else remarks		
			gl_doc.insert()


	def insert_gl_records_for_projects(self):
     
		default_company = frappe.db.get_single_value("Global Settings", "default_company")
		default_accounts = frappe.get_value(
			"Company",
			default_company,
			[
				"default_receivable_account",
				"default_inventory_account",
				"default_income_account",
				"cost_of_goods_sold_account",
				"round_off_account",
				"tax_account",
			],
			as_dict=1,
		)

		remarks = f"{self.payment_mode} Receipt"
		idx = 0
		project_account_wise_payment_total = {}  # For 'Other' receipt types
		project_customer_account_wise_return_total = {}  # For returns (#+ Customer + Account key)
		project_customer_account_wise_payment_total = {}  # For else cases (Project + Customer + Account key)
		project_on_account_payment_total = {}   # For On Account payments

		receipt_details = self.receipt_entry_details
		receipt_allocation = getattr(self, "receipt_allocation", None)	
		print("receipt_allocation")
		print(receipt_allocation)

		if receipt_details:
			for receipt_entry in receipt_details:
				 # Handle 'Other' Receipt Type (Project + Account-based)
				if receipt_entry.receipt_type == "Other":
					project_account_key = (receipt_entry.project, receipt_entry.account)
					project_account_wise_payment_total[project_account_key] = project_account_wise_payment_total.get(project_account_key, 0) + receipt_entry.amount

					print("project_account_wise_payment_total")
					print(project_account_wise_payment_total)

				# Handle Returns (Project + Customer + Account key)
				elif receipt_entry.reference_type in ["Sales Return", "Credit Note"]:
					if receipt_allocation:
						filtered_returns = [
							allocation
							for allocation in receipt_allocation
							if allocation.customer == receipt_entry.customer
							and allocation.reference_type == receipt_entry.reference_type
						]
						for allocation in filtered_returns:
							return_key = (allocation.project, allocation.customer, receipt_entry.account)
							project_customer_account_wise_return_total[return_key] = project_customer_account_wise_return_total.get(return_key, 0) + allocation.amount

				elif receipt_entry.reference_type  == "On Account":
					reference_key = (receipt_entry.project,receipt_entry.account)
					project_on_account_payment_total[reference_key] = project_on_account_payment_total.get(reference_key, 0) + receipt_entry.amount					
        
					# project_on_account_payment_total
				# Handle Allocations for Receipt Type "Customer!"
				elif receipt_entry.receipt_type == "Customer":
        
					if receipt_allocation:
						filtered_allocations = [
							allocation
							for allocation in receipt_allocation
							if allocation.customer == receipt_entry.customer
							and allocation.reference_type == receipt_entry.reference_type
						]
						for allocation in filtered_allocations:
							allocation_key = (allocation.project, allocation.customer, receipt_entry.account)
							project_customer_account_wise_payment_total[allocation_key] = project_customer_account_wise_payment_total.get(allocation_key, 0) + allocation.paying_amount

						print("project_customer_account_wise_payment_total")
						print(project_customer_account_wise_payment_total)

		# Function to create GL Posting for Debit and Credit
		def create_gl_postings(project, customer, account, amount, is_return=False):
			nonlocal idx

			remarks = ""

			if self.remarks:
				remarks = self.remarks
    
			elif project and customer:
				remarks = f"{self.payment_mode} receipt from {customer} for the project {project}"

			elif customer:
				remarks = f"{self.payment_mode} receipt from {customer}"

			else:
				remarks = f"{self.payment_mode} receipt"       
       
   
			if is_return:
				# Create credit entry for the return
				idx += 1
				gl_doc_credit = frappe.new_doc("GL Posting")
				gl_doc_credit.voucher_type = "Receipt Entry"
				gl_doc_credit.voucher_no = self.name
				gl_doc_credit.idx = idx
				gl_doc_credit.posting_date = self.posting_date
				gl_doc_credit.posting_time = self.posting_time
				gl_doc_credit.project = project
				gl_doc_credit.party_type = "Customer" if customer else None
				gl_doc_credit.party = customer
				gl_doc_credit.account = account  # Account from dictionary
				gl_doc_credit.debit_amount = amount
				gl_doc_credit.against_account = self.account
				gl_doc_credit.remarks = remarks
				gl_doc_credit.insert()

				# Create debit entry for the return
				idx += 1
				gl_doc_debit = frappe.new_doc("GL Posting")
				gl_doc_debit.voucher_type = "Receipt Entry"
				gl_doc_debit.voucher_no = self.name
				gl_doc_debit.idx = idx
				gl_doc_debit.posting_date = self.posting_date
				gl_doc_debit.posting_time = self.posting_time
				gl_doc_debit.project = project
				gl_doc_debit.account = self.account  # Account from `frm.doc.account`
				gl_doc_debit.credit_amount = amount
				gl_doc_debit.against_account = account
				gl_doc_debit.remarks = remarks
				gl_doc_debit.insert()
			else:
				# Create debit entry for payments
				idx += 1
				gl_doc_debit = frappe.new_doc("GL Posting")
				gl_doc_debit.voucher_type = "Receipt Entry"
				gl_doc_debit.voucher_no = self.name
				gl_doc_debit.idx = idx
				gl_doc_debit.posting_date = self.posting_date
				gl_doc_debit.posting_time = self.posting_time
				gl_doc_debit.project = project
				gl_doc_debit.party_type = "Customer" if customer else None
				gl_doc_debit.party = customer
				gl_doc_debit.account = account  # Account from dictionary
				gl_doc_debit.credit_amount = amount
				gl_doc_debit.against_account = self.account
				gl_doc_debit.remarks = remarks
				gl_doc_debit.insert()

				# Create credit entry for payments
				idx += 1
				gl_doc_credit = frappe.new_doc("GL Posting")
				gl_doc_credit.voucher_type = "Receipt Entry"
				gl_doc_credit.voucher_no = self.name
				gl_doc_credit.idx = idx
				gl_doc_credit.posting_date = self.posting_date
				gl_doc_credit.posting_time = self.posting_time
				gl_doc_credit.project = project
				gl_doc_credit.account = self.account  # Account from `frm.doc.account`
				gl_doc_credit.debit_amount = amount
				gl_doc_credit.against_account = account
				gl_doc_credit.remarks = remarks
				gl_doc_credit.insert()

		print("project_customer_account_wise_return_total")
		print(project_customer_account_wise_return_total)
		print("project_account_wise_payment_total")
		print(project_account_wise_payment_total)

		# Insert GL Entries for Returns
		for (project, customer, account), return_amount in project_customer_account_wise_return_total.items():
			create_gl_postings(project, customer, account, return_amount, is_return=True)

		# Insert GL Entries for 'Other' Payments
		for (project, account), payment_amount in project_account_wise_payment_total.items():
			create_gl_postings(project, None, account, payment_amount, is_return=False)
   
		# Insert GL Entries for 'On Account' Payments
		for (project, account), payment_amount in project_on_account_payment_total.items():
			create_gl_postings(project, None, account, payment_amount, is_return=False)

		# Insert GL Entries for Allocations
		for (project, customer, account), payment_amount in project_customer_account_wise_payment_total.items():
			create_gl_postings(project, customer, account, payment_amount, is_return=False)
	
	def on_trash(self):
		self.revert_documents_paid_amount_for_receipt()
		self.revert_for_advance_receipt()

	def on_cancel(self):
		cancel_bank_reconciliation("Receipt Entry", self.name)
		#print("from on cancel")
		self.revert_documents_paid_amount_for_receipt()

		delete_gl_postings_for_cancel_doc_type('Receipt Entry',self.name)
		self.revert_for_advance_receipt()

		# frappe.db.delete("GL Posting",
		# 		{"Voucher_type": "Receipt Entry",
		# 		"voucher_no": self.name
		# 		})

	def GetAccountForTheHighestAmountInPayments(self):

		highestAmount = 0
		account = ""

		receipt_details = self.receipt_entry_details

		if receipt_details:

			for receipt_entry in receipt_details:

				if receipt_entry.amount > highestAmount:
					highestAmount = receipt_entry.amount
					account = receipt_entry.account

		return account


	def revert_documents_paid_amount_for_receipt(self):
		#print("onl here")
		allocations = self.receipt_allocation
		previous_paid_amount = 0
		if(allocations):
			for allocation in allocations:
				#print("allocation.reference_type")
				#print(allocation.reference_type)

				if allocation.reference_type == "Sales Invoice":
					if(allocation.paying_amount>0):
						receipt_no = self.name
						if self.is_new():
							receipt_no = ""

						previous_paid_amount = 0
						allocations_exists = get_allocations_for_sales_invoice(allocation.reference_name, receipt_no)
						for existing_allocation in allocations_exists:
							previous_paid_amount = previous_paid_amount +  existing_allocation.paying_amount

						total_paid_Amount = previous_paid_amount
						frappe.db.set_value("Sales Invoice", allocation.reference_name, {'paid_amount': total_paid_Amount})
      
				if allocation.reference_type == "Progressive Sales Invoice":
					if(allocation.paying_amount>0):
						receipt_no = self.name
						if self.is_new():
							receipt_no = ""

						previous_paid_amount = 0
						allocations_exists = get_allocations_for_progressive_sales_invoice(allocation.reference_name, receipt_no)
						for existing_allocation in allocations_exists:
							previous_paid_amount = previous_paid_amount +  existing_allocation.paying_amount

						total_paid_Amount = previous_paid_amount
						frappe.db.set_value("Sales Invoice", allocation.reference_name, {'paid_amount': total_paid_Amount})

				if allocation.reference_type == "Sales Return":
					if(allocation.paying_amount>0):
						receipt_no = self.name
						if self.is_new():
							receipt_no = ""

						previous_paid_amount = 0
						allocations_exists = get_allocations_for_sales_return(allocation.reference_name, receipt_no)
						for existing_allocation in allocations_exists:
							previous_paid_amount = previous_paid_amount +  existing_allocation.paying_amount

						total_paid_Amount = previous_paid_amount
						frappe.db.set_value("Sales Return", allocation.reference_name, {'paid_amount': total_paid_Amount})
      
				if allocation.reference_type == "Sales Order":
					if(allocation.paying_amount>0):
						receipt_no = self.name
						if self.is_new():
							receipt_no = ""

						# previous_paid_amount = 0
						# allocations_exists = get_allocations_for_sales_invoice(allocation.reference_name, receipt_no)
						# for existing_allocation in allocations_exists:
						# 	previous_paid_amount = previous_paid_amount +  existing_allocation.paying_amount

						total_paid_Amount = previous_paid_amount
						frappe.db.set_value("Sales Order", allocation.reference_name, {'paid_amount': 0})

@frappe.whitelist()
def get_amount(receipt_entry_id):
    amt = frappe.db.get_value('Receipt Entry', receipt_entry_id, 'amount')

    return amt

@frappe.whitelist()
def receipt_allocation_updates(receipt_entry_id, sales_inv_id):
    receipt_entry = frappe.get_doc("Receipt Entry", receipt_entry_id)
    sales_inv_doc = frappe.get_doc("Sales Invoice", sales_inv_id)
    
    # Check if the row already exists in receipt_allocation_copy
    row_exists = False
    for row in receipt_entry.receipt_allocation_copy:
        if (row.reference_type == "Sales Invoice" and
            row.reference_name == sales_inv_id and
            row.customer == sales_inv_doc.customer and
            row.total_amount == sales_inv_doc.net_total):
            row_exists = True
            break
    
    if not row_exists:
        # Append a new row to receipt_allocation_copy
        receipt_entry.allocated_amount = sales_inv_doc.net_total
        new_row = receipt_entry.append("receipt_allocation_copy", {
            "reference_type": "Sales Invoice",
            "reference_name": sales_inv_id,
            "customer": sales_inv_doc.customer,
            "total_amount": sales_inv_doc.net_total
        })
        
        # Save the document to persist changes
        receipt_entry.save()
        
        return "Row added successfully"
    else:
        return "Row already exists, no action taken"

