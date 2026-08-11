"""Identity: registration, login, password hashing, JWT issuance/verification.

Authorization (roles/permissions) is a separate concern - see app/rbac/.
Nothing in this package knows what a "permission" is; it only answers
"who is this token for, and is it still valid."
"""
