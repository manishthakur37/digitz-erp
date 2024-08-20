# Copyright (c) 2023, Rupesh P and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class UserWarehouse(Document):

	def validate(self):

		possible_invalid= frappe.db.count('User Warehouse', {'user': ['=', self.user], 'warehouse':['=', self.warehouse]})

		if(possible_invalid >0):
			frappe.throw("Duplicate record found. Cannot continue.")

		any_user= frappe.db.count('User Warehouse', {'user': ['=', self.user]})

		if(any_user == 0):
			self.is_default = 1

@frappe.whitelist()
def check_user_entry(user):
    user_warehouse_entry = frappe.db.exists("User Warehouse", {"user": user})
    #print('user_warehouse_entry:', user_warehouse_entry)
    if user_warehouse_entry:
        return True
    else:
        return False
