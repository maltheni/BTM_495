#!/usr/bin/env python
"""Run the Spinelli Kia final prototype:  python manage.py runserver   then open http://127.0.0.1:8000"""
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "spinelli_web.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
