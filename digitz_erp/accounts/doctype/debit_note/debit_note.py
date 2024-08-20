# Copyright (c) 2023, Rupesh P and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import money_in_words
from digitz_erp.api.gl_posting_api import update_accounts_for_doc_type, delete_gl_postings_for_cancel_doc_type
from digitz_erp.api.settings_api import get_gl_narration

class DebitNote(Document):

	def before_validate(self):
		self.in_words = money_in_words(self.grand_total,"AED")

	def on_submit(self):
		# frappe.enqueue(self.do_postings_on_submit, queue="long")
		self.do_postings_on_submit()

	def on_update(self):
		self.update_payment_schedules()

	def on_cancel(self):
		self.do_cancel_debit_note()

	def do_postings_on_submit(self):

		self.insert_gl_records()
		update_accounts_for_doc_type('Debit Note',self.name)

	def update_payment_schedules(self):
		existing_entries = frappe.get_all("Payment Schedule", filters={"payment_against": "Debit", "document_no": self.name})
		for entry in existing_entries:
			try:
				frappe.delete_doc("Payment Schedule", entry.name)
			except Exception as e:
				frappe.log_error("Error deleting payment schedule: " + str(e))
		if self.on_credit and self.payment_schedule:
			for schedule in self.payment_schedule:
				new_payment_schedule = frappe.new_doc("Payment Schedule")
				new_payment_schedule.payment_against = "Debit"
				new_payment_schedule.supplier = self.supplier
				new_payment_schedule.document_no = self.name
				new_payment_schedule.document_date = self.date
				new_payment_schedule.scheduled_date = schedule.date
				new_payment_schedule.amount = schedule.amount

				try:
					new_payment_schedule.insert()
				except Exception as e:
					frappe.log_error("Error creating payment schedule: " + str(e))
     
	def get_narration(self):
		
		# Assign supplier, invoice_no, and remarks
		supplier_name = self.supplier
		#print("supplier_name")
		#print(supplier_name)
		remarks = self.remarks if self.remarks else ""
		payment_mode = ""
		if self.on_credit:
			payment_mode = "Credit"
		else:
			payment_mode = self.payment_mode
		
		# Get the gl_narration which might be empty
		gl_narration = get_gl_narration('Debit Note')  # This could return an empty string

		# Provide a default template if gl_narration is empty
		if not gl_narration:
			gl_narration = f"Debit Note to {supplier_name}"
   

		# Replace placeholders with actual values
		narration = gl_narration.format(supplier=supplier_name)  
		#print("supplier_name")
  

		#print("narration")
		#print(narration)
	

		# Append remarks if they are available
		if remarks:
			narration += f", {remarks}"

		return narration   

	def insert_gl_records(self):
     
		remarks = self.get_narration()

		idx = 1

		highestAccount = self.GetAccountForTheHighestAmount()

		gl_doc = frappe.new_doc('GL Posting')
		gl_doc.idx = idx
		gl_doc.voucher_type = 'Debit Note'
		gl_doc.voucher_no = self.name
		gl_doc.posting_date = self.date
		gl_doc.account = self.payable_account
		gl_doc.debit_amount = self.grand_total
		gl_doc.against_account = highestAccount
		gl_doc.remarks = self.remarks
		gl_doc.party_type = "Supplier"
		gl_doc.party = self.supplier
		gl_doc.remarks = remarks
		gl_doc.insert()

		tax_ledgers = {}

		for debit_note_detail in self.debit_note_details:

			idx = idx + 1
			gl_doc = frappe.new_doc('GL Posting')
			gl_doc.idx = idx
			gl_doc.voucher_type = 'Debit Note'
			gl_doc.voucher_no = self.name
			gl_doc.posting_date = self.date
			gl_doc.account = debit_note_detail.account
			gl_doc.credit_amount = debit_note_detail.amount_excluded_tax
			gl_doc.against_account = self.payable_account
			gl_doc.remarks = remarks
			gl_doc.insert()

			if not debit_note_detail.tax_excluded and debit_note_detail.tax_amount > 0:
				if debit_note_detail.tax_account not in tax_ledgers:
					tax_ledgers[debit_note_detail.tax_account] = debit_note_detail.tax_amount
				else:
					tax_ledgers[debit_note_detail.tax_account] += debit_note_detail.tax_amount

		for tax_account,tax_amount in tax_ledgers.items():

			if tax_amount >0:
				idx = idx + 1
				gl_doc = frappe.new_doc('GL Posting')
				gl_doc.idx = idx
				gl_doc.voucher_type = 'Debit Note'
				gl_doc.voucher_no = self.name
				gl_doc.posting_date = self.date
				gl_doc.account = tax_account
				gl_doc.credit_amount = tax_amount
				gl_doc.against_account = self.payable_account
				gl_doc.remarks = remarks
				gl_doc.insert()

		# For payments
		if not self.on_credit:
			idx = idx + 1
			gl_doc = frappe.new_doc('GL Posting')
			gl_doc.idx = idx
			gl_doc.voucher_type = 'Debit Note'
			gl_doc.voucher_no = self.name
			gl_doc.posting_date = self.date
			gl_doc.account = self.payable_account
			gl_doc.credit_amount = self.grand_total
			gl_doc.against_account = self.payment_account			
			gl_doc.party_type = "Supplier"
			gl_doc.party = self.supplier
			gl_doc.remarks = remarks
			gl_doc.insert()

			idx = idx + 1
			gl_doc = frappe.new_doc('GL Posting')
			gl_doc.idx = idx
			gl_doc.voucher_type = 'Debit Note'
			gl_doc.voucher_no = self.name
			gl_doc.posting_date = self.date
			gl_doc.account = self.payment_account
			gl_doc.debit_amount = self.grand_total
			gl_doc.against_account = self.payable_account
			gl_doc.remarks = remarks
			gl_doc.insert()

	def GetAccountForTheHighestAmount(self):

		highestAmount = 0
		account = ""

		payment_details = self.debit_note_details

		for detail in self.debit_note_details:

			if detail.amount > highestAmount:
				highestAmount = detail.amount
				account = detail.account

		return account

	def do_cancel_debit_note(self):

		delete_gl_postings_for_cancel_doc_type('Debit Note',self.name)

		# frappe.db.delete("GL Posting",
        #                  {"Voucher_type": "Debit Note",
        #                   "voucher_no": self.name
        #                   })
@frappe.whitelist()
def get_default_payment_mode():
    default_payment_mode = frappe.db.get_value('Company', filters={'name'},fieldname='default_payment_mode_for_purchase')
    #print(default_payment_mode)
    return default_payment_mode

@frappe.whitelist()
def get_gl_postings(debit_note):
    gl_postings = frappe.get_all("GL Posting",
                                  filters={"voucher_no": debit_note},
                                  fields=["name", "debit_amount", "credit_amount", "against_account", "remarks"])
    formatted_gl_postings = []
    for posting in gl_postings:
        formatted_gl_postings.append({
            "gl_posting": posting.name,
            "debit_amount": posting.debit_amount,
            "credit_amount": posting.credit_amount,
            "against_account": posting.against_account,
            "remarks": posting.remarks
        })

    return formatted_gl_postings
