#!/usr/bin/env python
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trust_service.settings')
from django.core.management import execute_from_command_line
execute_from_command_line(sys.argv)
