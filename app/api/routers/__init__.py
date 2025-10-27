# app/api/routers/__init__.py
"""
API routers package
"""

from . import (
    auth,
    schools,
    chat,
    students,
    classes,
    academic,
    fees,
    invoices,
    payments,
    guardians,
    notifications,
    enrollments,
    rasa_content,
    users
)

__all__ = [
    "auth",
    "schools",
    "chat",
    "students",
    "classes",
    "academic",
    "fees",
    "invoices",
    "payments",
    "guardians",
    "notifications",
    "enrollments",
    "rasa_content",
    "users"
]